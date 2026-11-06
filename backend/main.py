import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Literal

import httpx
import jwt
from dotenv import load_dotenv
from email_validator import validate_email, EmailNotValidError
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pydantic import BaseModel, Field, EmailStr
from sqlalchemy.exc import IntegrityError

from backend.rag import search_transcripts
from backend.database import (
    SessionLocal,
    User,
    Conversation,
    ChatMessage,
    GeneratedArtifact,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lenny-assistant")

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OLLAMA_PROXY_TOKEN = os.getenv("OLLAMA_PROXY_TOKEN", "").strip()

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash").strip()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "").strip()
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()

password_hash = PasswordHash.recommended()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/login",
    auto_error=False,
)


# ---------------------------------------------------------
# GEMINI RESPONSE HELPERS
# ---------------------------------------------------------

def extract_gemini_text(data: dict, task_name: str) -> str:
    """Extract text from a Gemini response."""

    prompt_feedback = data.get("promptFeedback") or {}
    block_reason = prompt_feedback.get("blockReason")

    if block_reason:
        logger.warning(
            "Gemini blocked the %s prompt: %s",
            task_name,
            block_reason,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini could not process this request. "
                "Please rephrase it and try again."
            ),
        )

    candidates = data.get("candidates") or []

    if not candidates:
        logger.error(
            "Gemini returned no candidates for %s. Response keys: %s",
            task_name,
            list(data.keys()),
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini did not return an answer. "
                "Please try again."
            ),
        )

    candidate = candidates[0]
    finish_reason = str(candidate.get("finishReason", "")).upper()

    content = candidate.get("content") or {}
    parts = content.get("parts") or []

    text_parts = []

    for part in parts:
        if not isinstance(part, dict):
            continue

        if part.get("thought") is True:
            continue

        part_text = part.get("text")

        if isinstance(part_text, str) and part_text.strip():
            text_parts.append(part_text.strip())

    answer = "\n\n".join(text_parts).strip()

    if finish_reason == "MAX_TOKENS":
        logger.warning(
            "Gemini reached the output-token limit during %s. "
            "Partial output length: %s",
            task_name,
            len(answer),
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini reached its response-length limit before "
                "finishing. Please retry with a shorter or more "
                "focused request."
            ),
        )

    if finish_reason in {"SAFETY", "BLOCKLIST", "PROHIBITED_CONTENT"}:
        logger.warning(
            "Gemini stopped the %s response: %s",
            task_name,
            finish_reason,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini could not complete this response. "
                "Please rephrase your request."
            ),
        )

    if not answer:
        logger.error(
            "Gemini returned no text for %s. Finish reason: %s",
            task_name,
            finish_reason or "unknown",
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "Gemini returned an empty response. "
                "Please try again."
            ),
        )

    return answer


def gemini_error_message(response: httpx.Response) -> str:
    """Extract a useful error without exposing secrets."""

    try:
        data = response.json()
        error = data.get("error") or {}
        message = error.get("message")

        if isinstance(message, str) and message.strip():
            return message[:500]

    except (ValueError, AttributeError):
        pass

    return "No additional error information was provided."


# ---------------------------------------------------------
# AUTHENTICATION HELPERS
# ---------------------------------------------------------

def create_access_token(user_id: int) -> str:
    if not JWT_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured.",
        )

    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )


def get_current_user(
    token: str | None = Depends(oauth2_scheme),
) -> User | None:
    """Return the authenticated user, or None for a guest."""

    if not token:
        return None

    if not JWT_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured.",
        )

    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
        )
        user_id = int(payload["sub"])

    except (InvalidTokenError, KeyError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    db = SessionLocal()

    try:
        user = db.get(User, user_id)

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Account not found.",
            )

        return user

    finally:
        db.close()


def require_user(
    user: User | None = Depends(get_current_user),
) -> User:
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Please sign in to access this feature.",
        )

    return user


def normalize_email(email: str) -> str:
    try:
        result = validate_email(
            email,
            check_deliverability=False,
        )
        return result.normalized.lower()

    except EmailNotValidError:
        raise HTTPException(
            status_code=422,
            detail="Please enter a valid email address.",
        )


def auth_response(user: User) -> dict:
    return {
        "access_token": create_access_token(user.id),
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "email": user.email,
        },
    }


# ---------------------------------------------------------
# DATABASE HELPERS
# ---------------------------------------------------------

def save_chat_exchange(
    session_id: str,
    user_id: int,
    user_message: str,
    assistant_message: str,
    provider: str,
):
    """Save a chat exchange belonging to one account."""

    db = SessionLocal()

    try:
        conversation = db.get(Conversation, session_id)

        if conversation is not None and conversation.user_id != user_id:
            raise HTTPException(
                status_code=409,
                detail="This conversation does not belong to your account.",
            )

        if conversation is None:
            conversation = Conversation(
                id=session_id,
                user_id=user_id,
                title=user_message[:100],
            )
            db.add(conversation)

        conversation.updated_at = datetime.now(timezone.utc)

        db.add_all([
            ChatMessage(
                conversation_id=session_id,
                role="user",
                content=user_message,
                provider=provider,
            ),
            ChatMessage(
                conversation_id=session_id,
                role="assistant",
                content=assistant_message,
                provider=provider,
            ),
        ])

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


def save_generated_artifact(
    session_id: str,
    user_id: int,
    title: str,
    content: str,
    provider: str,
):
    """Save an essay belonging to one account."""

    db = SessionLocal()

    try:
        conversation = db.get(Conversation, session_id)

        if conversation is not None and conversation.user_id != user_id:
            raise HTTPException(
                status_code=409,
                detail="This conversation does not belong to your account.",
            )

        if conversation is None:
            conversation = Conversation(
                id=session_id,
                user_id=user_id,
                title=title[:100],
            )
            db.add(conversation)
            db.flush()

        conversation.updated_at = datetime.now(timezone.utc)

        db.add(
            GeneratedArtifact(
                conversation_id=session_id,
                title=title,
                content=content,
                artifact_type="markdown",
                provider=provider,
            )
        )

        db.commit()

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()


# ---------------------------------------------------------
# APP CONFIGURATION
# ---------------------------------------------------------

app = FastAPI(
    title="The Lenny Growth Assistant",
    description="An AI assistant for product and growth questions.",
    version="0.5.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://lenny-growth-assistant-jet.vercel.app",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# REQUEST AND RESPONSE MODELS
# ---------------------------------------------------------

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class GoogleLoginRequest(BaseModel):
    credential: str = Field(min_length=20)


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    session_id: str = Field(default="default", min_length=1, max_length=100)
    history: list[Message] = Field(default_factory=list, max_length=20)
    provider: Literal["ollama", "gemini"] = "ollama"


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    provider: str
    timestamp: str
    sources: list[dict] = Field(default_factory=list)


class EssayRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    audience: str = Field(
        default="product managers and startup founders",
        max_length=300,
    )
    provider: Literal["ollama", "gemini"] = "ollama"
    session_id: str = Field(default="default", min_length=1, max_length=100)


class EssayResponse(BaseModel):
    title: str
    markdown: str
    provider: str
    timestamp: str


# ---------------------------------------------------------
# HEALTH AND MODEL ENDPOINTS
# ---------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "lenny-growth-assistant",
    }


@app.get("/api/models")
async def models():
    return {
        "models": [
            {
                "provider": "ollama",
                "model": OLLAMA_MODEL,
                "local": True,
                "configured": True,
            },
            {
                "provider": "gemini",
                "model": GEMINI_MODEL,
                "local": False,
                "configured": bool(GEMINI_API_KEY),
            },
        ]
    }


# ---------------------------------------------------------
# EMAIL AND PASSWORD AUTHENTICATION
# ---------------------------------------------------------

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    email = normalize_email(str(request.email))

    if not JWT_SECRET_KEY:
        raise HTTPException(
            status_code=503,
            detail="Authentication is not configured.",
        )

    db = SessionLocal()

    try:
        existing = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if existing:
            raise HTTPException(
                status_code=409,
                detail="An account with this email already exists.",
            )

        user = User(
            email=email,
            password_hash=password_hash.hash(request.password),
        )

        db.add(user)
        db.commit()
        db.refresh(user)

        return auth_response(user)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="An account with this email already exists.",
        )

    finally:
        db.close()


@app.post("/api/auth/login")
async def login(request: LoginRequest):
    email = normalize_email(str(request.email))

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.email == email)
            .first()
        )

        if (
            user is None
            or user.password_hash is None
            or not password_hash.verify(
                request.password,
                user.password_hash,
            )
        ):
            raise HTTPException(
                status_code=401,
                detail="Incorrect email or password.",
            )

        return auth_response(user)

    finally:
        db.close()


# ---------------------------------------------------------
# GOOGLE SIGN-IN
# ---------------------------------------------------------

@app.post("/api/auth/google")
async def google_login(request: GoogleLoginRequest):
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured yet.",
        )

    try:
        claims = id_token.verify_oauth2_token(
            request.credential,
            google_requests.Request(),
            GOOGLE_CLIENT_ID,
        )

        email = normalize_email(claims.get("email", ""))

        if claims.get("email_verified") is not True:
            raise HTTPException(
                status_code=401,
                detail="Google email is not verified.",
            )

        google_id = claims.get("sub")

        if not google_id:
            raise HTTPException(
                status_code=401,
                detail="Invalid Google account.",
            )

    except HTTPException:
        raise

    except Exception:
        logger.exception("Google token verification failed")

        raise HTTPException(
            status_code=401,
            detail="Google sign-in verification failed.",
        )

    db = SessionLocal()

    try:
        user = (
            db.query(User)
            .filter(User.google_id == google_id)
            .first()
        )

        if user is None:
            user = (
                db.query(User)
                .filter(User.email == email)
                .first()
            )

            if user is not None:
                if user.google_id and user.google_id != google_id:
                    raise HTTPException(
                        status_code=409,
                        detail="This email is linked to another Google account.",
                    )

                user.google_id = google_id

            else:
                user = User(
                    email=email,
                    google_id=google_id,
                    password_hash=None,
                )
                db.add(user)

        db.commit()
        db.refresh(user)

        return auth_response(user)

    except HTTPException:
        db.rollback()
        raise

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Could not create or link this Google account.",
        )

    finally:
        db.close()


@app.get("/api/auth/me")
async def get_me(user: User = Depends(require_user)):
    return {
        "id": user.id,
        "email": user.email,
    }


# ---------------------------------------------------------
# AI INSTRUCTIONS AND RAG
# ---------------------------------------------------------

def build_instructions(sources: list[dict]) -> str:
    instructions = (
        "You are The Lenny Growth Assistant. "
        "Answer questions about product management, startups, "
        "growth, experimentation, and leadership. "
        "Use conversation history for follow-up questions. "

        "RESPONSE STYLE: "
        "Be concise and answer the exact question. "
        "For simple questions and definitions, use 1-3 sentences "
        "and aim for fewer than 50 words. "
        "Give the direct answer first. "
        "Do not add unnecessary headings, introductions, conclusions, "
        "examples, lists, or background information. "
        "Only explain further when the user asks for detail. "
        "For complex questions, use short paragraphs and relevant bullets. "

        "PODCAST SOURCES: "
        "Use transcript excerpts when relevant. "
        "Cite evidence using the exact source filename. "
        "Never invent citations, statistics, quotes, or episode details. "
        "If no transcript matches, answer using general knowledge. "
        "Do not mention missing transcripts or add disclaimers. "
        "Never claim general knowledge came from a podcast."
    )

    if sources:
        source_text = "\n\n".join(
            f"Episode: {item['episode']}\n"
            f"Source file: {item['source']}\n"
            f"Excerpt: {item['text']}"
            for item in sources
        )
    else:
        source_text = (
            "No matching transcript excerpts were found. "
            "Use general knowledge without claiming podcast support."
        )

    return (
        instructions
        + "\n\nPODCAST TRANSCRIPT SEARCH RESULTS:\n"
        + source_text
    )


# ---------------------------------------------------------
# CHAT ENDPOINT
# ---------------------------------------------------------

@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    user: User | None = Depends(get_current_user),
):
    sources = search_transcripts(
        request.message,
        top_k=4,
    )

    instructions = build_instructions(sources)

    conversation = [
        {
            "role": item.role,
            "content": item.content,
        }
        for item in request.history[-10:]
    ]

    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:

            # ---------------------------------------------
            # GEMINI
            # ---------------------------------------------

            if request.provider == "gemini":

                if not GEMINI_API_KEY:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Gemini is not configured. "
                            "Configure GEMINI_API_KEY."
                        ),
                    )

                gemini_contents = [
                    {
                        "role": (
                            "model"
                            if item["role"] == "assistant"
                            else "user"
                        ),
                        "parts": [
                            {"text": item["content"]}
                        ],
                    }
                    for item in conversation
                ]

                gemini_contents.append(
                    {
                        "role": "user",
                        "parts": [
                            {"text": request.message}
                        ],
                    }
                )

                # Retry once for temporary Gemini errors.
                for attempt in range(2):
                    response = await client.post(
                        (
                            "https://generativelanguage.googleapis.com/"
                            f"v1beta/models/{GEMINI_MODEL}:generateContent"
                        ),
                        headers={
                            "x-goog-api-key": GEMINI_API_KEY,
                            "Content-Type": "application/json",
                        },
                        json={
                            "systemInstruction": {
                                "parts": [
                                    {"text": instructions}
                                ],
                            },
                            "contents": gemini_contents,
                            "generationConfig": {
                                 "maxOutputTokens": 2048,
                                 "temperature": 0.5,
                                 "thinkingConfig": {
                                      "thinkingLevel": "LOW",
                                  },
                             },
                        },
                    )

                    if response.is_success:
                        break

                    if (
                        response.status_code in (429, 500, 502, 503, 504)
                        and attempt == 0
                    ):
                        logger.warning(
                            "Gemini temporarily unavailable. Retrying once."
                        )
                        await asyncio.sleep(3)
                        continue

                    break

                if not response.is_success:
                    error_message = gemini_error_message(response)

                    logger.error(
                        "Gemini chat request failed after retry check. "
                        "HTTP %s: %s",
                        response.status_code,
                        error_message,
                    )

                response.raise_for_status()

                data = response.json()

                answer = extract_gemini_text(
                    data,
                    "chat",
                )

                provider_name = f"gemini/{GEMINI_MODEL}"

            # ---------------------------------------------
            # OLLAMA
            # ---------------------------------------------

            else:

                history_text = "\n\n".join(
                    f"{item['role'].capitalize()}: {item['content']}"
                    for item in conversation
                )

                prompt = (
                    instructions
                    + "\n\n"
                    + history_text
                    + "\n\nUser: "
                    + request.message
                    + "\n\nAssistant:"
                )

                response = await client.post(
                    f"{OLLAMA_URL.rstrip('/')}/api/generate",
                    headers={
                        "Authorization": f"Bearer {OLLAMA_PROXY_TOKEN}"
                    },
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": "10m",
                        "options": {
                            "num_predict": 700,
                        },
                    },
                )

                response.raise_for_status()

                data = response.json()

                answer = (data.get("response") or "").strip()

                provider_name = f"ollama/{OLLAMA_MODEL}"

        if not answer:
            raise HTTPException(
                status_code=502,
                detail="The selected model returned an empty answer.",
            )

        # Guest chats are deliberately never saved.
        if user is not None:
            try:
                save_chat_exchange(
                    session_id=request.session_id,
                    user_id=user.id,
                    user_message=request.message,
                    assistant_message=answer,
                    provider=provider_name,
                )

            except HTTPException:
                raise

            except Exception:
                logger.exception(
                    "Chat succeeded but saving history failed"
                )

        return ChatResponse(
            answer=answer,
            session_id=request.session_id,
            provider=provider_name,
            timestamp=timestamp,
            sources=[
                {
                    "episode": item["episode"],
                    "source": item["source"],
                    "score": item["score"],
                }
                for item in sources
            ],
        )

    except HTTPException:
        raise

    except httpx.ConnectError:
        logger.exception(
            "Could not connect to the selected AI provider"
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Could not connect to the selected AI provider. "
                "Check that the service is running and reachable."
            ),
        )

    except httpx.TimeoutException:
        logger.exception(
            "AI provider request timed out"
        )

        raise HTTPException(
            status_code=504,
            detail="The model took too long to respond. Please retry.",
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "AI provider returned HTTP %s",
            exc.response.status_code,
        )

        if request.provider == "gemini":
            if exc.response.status_code in (429, 500, 502, 503, 504):
                detail = (
                    "Gemini is temporarily experiencing high demand. "
                    "Please try again shortly or switch to Ollama."
                )
            else:
                detail = gemini_error_message(exc.response)

            raise HTTPException(
                status_code=502,
                detail=f"Gemini API error: {detail}",
            )

        raise HTTPException(
            status_code=502,
            detail=(
                "The selected AI provider returned an error "
                f"(HTTP {exc.response.status_code}). "
                "Check its configuration."
            ),
        )

    except (ValueError, KeyError, IndexError, TypeError):
        logger.exception(
            "Could not parse the model response"
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "The selected AI provider returned an invalid response."
            ),
        )


# ---------------------------------------------------------
# SHIP 30 ESSAY GENERATION
# ---------------------------------------------------------

@app.post("/api/ship-30", response_model=EssayResponse)
async def generate_ship_30(
    request: EssayRequest,
    user: User | None = Depends(get_current_user),
):
    """Generate an essay. Save it only for signed-in users."""

    instructions = f"""
You are an experienced essay writer creating a Ship 30 for 30-style essay.

TOPIC: {request.topic}
TARGET AUDIENCE: {request.audience}

Write approximately 1,250 words, aiming for 1,100 to 1,400 words.

STRUCTURE:
1. Begin with a compelling, concrete hook.
2. Introduce one clear central argument.
3. Develop a logical narrative with useful Markdown headings.
4. Use short paragraphs, specific examples, and practical explanations.
5. Explain why the ideas matter to the audience.
6. End with one specific, actionable takeaway.

FACTUAL ACCURACY:
- Never invent statistics, studies, citations, quotations, or research findings.
- Do not attribute claims to real companies or people without reliable support.
- Do not imply the essay is based on podcast transcripts.
- Clearly identify hypothetical examples.
- Prefer clear reasoning over unsupported claims.
- Avoid repetitive introductions and conclusions.

OUTPUT:
Return Markdown only.
Begin with a single # title.
Use ## headings for major sections.
Finish with a clearly labeled "Actionable Takeaway" section.
"""

    try:
        async with httpx.AsyncClient(timeout=240.0) as client:

            # ---------------------------------------------
            # GEMINI
            # ---------------------------------------------

            if request.provider == "gemini":

                if not GEMINI_API_KEY:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "Gemini is not configured. "
                            "Configure GEMINI_API_KEY."
                        ),
                    )

                response = await client.post(
                    (
                        "https://generativelanguage.googleapis.com/"
                        f"v1beta/models/{GEMINI_MODEL}:generateContent"
                    ),
                    headers={
                        "x-goog-api-key": GEMINI_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={
                        "systemInstruction": {
                            "parts": [
                                {"text": instructions}
                            ],
                        },
                        "contents": [
                            {
                                "role": "user",
                                "parts": [
                                    {"text": "Write the essay now."}
                                ],
                            }
                        ],
                        "generationConfig": {
                            "maxOutputTokens": 8192,
                            "temperature": 0.7,
                        },
                    },
                )

                if not response.is_success:
                    error_message = gemini_error_message(response)

                    logger.error(
                        "Gemini essay request failed. HTTP %s: %s",
                        response.status_code,
                        error_message,
                    )

                response.raise_for_status()

                data = response.json()

                markdown = extract_gemini_text(
                    data,
                    "essay generation",
                )

                provider_name = f"gemini/{GEMINI_MODEL}"

            # ---------------------------------------------
            # OLLAMA
            # ---------------------------------------------

            else:

                response = await client.post(
                    f"{OLLAMA_URL.rstrip('/')}/api/generate",
                    headers={
                        "Authorization": f"Bearer {OLLAMA_PROXY_TOKEN}"
                    },
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": (
                            instructions
                            + "\n\nWrite the essay now:"
                        ),
                        "stream": False,
                        "keep_alive": "10m",
                        "options": {
                            "num_predict": 3000,
                        },
                    },
                )

                response.raise_for_status()

                data = response.json()

                markdown = (data.get("response") or "").strip()

                provider_name = f"ollama/{OLLAMA_MODEL}"

        if not markdown:
            raise HTTPException(
                status_code=502,
                detail="The model returned an empty essay.",
            )

        title = next(
            (
                line[2:].strip()
                for line in markdown.splitlines()
                if line.startswith("# ")
            ),
            request.topic,
        )

        # Guest essays are returned but never saved.
        if user is not None:
            try:
                save_generated_artifact(
                    session_id=request.session_id,
                    user_id=user.id,
                    title=title,
                    content=markdown,
                    provider=provider_name,
                )

            except HTTPException:
                raise

            except Exception:
                logger.exception(
                    "Essay generated but saving it failed"
                )

        return EssayResponse(
            title=title,
            markdown=markdown,
            provider=provider_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise

    except httpx.TimeoutException:
        logger.exception(
            "Essay generation timed out"
        )

        raise HTTPException(
            status_code=504,
            detail="Essay generation timed out. Try again.",
        )

    except httpx.ConnectError:
        logger.exception(
            "Could not connect to the selected provider"
        )

        raise HTTPException(
            status_code=503,
            detail="Could not connect to the selected AI provider.",
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "Essay provider returned HTTP %s",
            exc.response.status_code,
        )

        if request.provider == "gemini":
            detail = gemini_error_message(exc.response)

            raise HTTPException(
                status_code=502,
                detail=f"Gemini API error: {detail}",
            )

        raise HTTPException(
            status_code=502,
            detail=(
                f"The AI provider returned HTTP {exc.response.status_code}."
            ),
        )

    except (ValueError, KeyError, IndexError, TypeError):
        logger.exception(
            "Could not parse the essay response"
        )

        raise HTTPException(
            status_code=502,
            detail="The AI provider returned an invalid essay response.",
        )


# ---------------------------------------------------------
# PRIVATE CONVERSATION HISTORY
# ---------------------------------------------------------

@app.get("/api/conversations")
async def list_conversations(
    user: User | None = Depends(get_current_user),
):
    """Guests receive an empty history. Users see only their own."""

    if user is None:
        return {"conversations": []}

    db = SessionLocal()

    try:
        conversations = (
            db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .order_by(Conversation.updated_at.desc())
            .all()
        )

        return {
            "conversations": [
                {
                    "id": item.id,
                    "title": item.title,
                    "created_at": item.created_at.isoformat(),
                    "updated_at": item.updated_at.isoformat(),
                    "message_count": len(item.messages),
                }
                for item in conversations
            ]
        }

    except Exception:
        logger.exception(
            "Failed to list conversations"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not load conversation history.",
        )

    finally:
        db.close()


@app.get("/api/conversations/{session_id}")
async def get_conversation(
    session_id: str,
    user: User = Depends(require_user),
):
    """Return a conversation only when it belongs to this user."""

    db = SessionLocal()

    try:
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == session_id,
                Conversation.user_id == user.id,
            )
            .first()
        )

        if conversation is None:
            raise HTTPException(
                status_code=404,
                detail="Conversation not found.",
            )

        return {
            "id": conversation.id,
            "title": conversation.title,
            "created_at": conversation.created_at.isoformat(),
            "updated_at": conversation.updated_at.isoformat(),
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "provider": message.provider,
                    "created_at": message.created_at.isoformat(),
                }
                for message in conversation.messages
            ],
        }

    except HTTPException:
        raise

    except Exception:
        logger.exception(
            "Failed to load conversation"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not load this conversation.",
        )

    finally:
        db.close()


# ---------------------------------------------------------
# PRIVATE GENERATED ESSAYS
# ---------------------------------------------------------

@app.get("/api/artifacts")
async def list_artifacts(
    user: User | None = Depends(get_current_user),
):
    """Guests receive no saved essays. Users see only their own."""

    if user is None:
        return {"artifacts": []}

    db = SessionLocal()

    try:
        artifacts = (
            db.query(GeneratedArtifact)
            .join(
                Conversation,
                GeneratedArtifact.conversation_id == Conversation.id,
            )
            .filter(Conversation.user_id == user.id)
            .order_by(GeneratedArtifact.created_at.desc())
            .all()
        )

        return {
            "artifacts": [
                {
                    "id": item.id,
                    "conversation_id": item.conversation_id,
                    "title": item.title,
                    "content": item.content,
                    "type": item.artifact_type,
                    "provider": item.provider,
                    "created_at": item.created_at.isoformat(),
                }
                for item in artifacts
            ]
        }

    except Exception:
        logger.exception(
            "Failed to list saved essays"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not load saved essays.",
        )

    finally:
        db.close()


# ---------------------------------------------------------
# CLEAR ONLY THE SIGNED-IN USER'S HISTORY
# ---------------------------------------------------------

@app.delete("/api/history")
async def clear_my_history(
    user: User = Depends(require_user),
):
    """Delete only the signed-in user's messages, essays and conversations."""

    db = SessionLocal()

    try:
        conversation_ids = (
            db.query(Conversation.id)
            .filter(Conversation.user_id == user.id)
            .subquery()
        )

        deleted_messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.conversation_id.in_(conversation_ids)
            )
            .delete(synchronize_session=False)
        )

        deleted_artifacts = (
            db.query(GeneratedArtifact)
            .filter(
                GeneratedArtifact.conversation_id.in_(conversation_ids)
            )
            .delete(synchronize_session=False)
        )

        deleted_conversations = (
            db.query(Conversation)
            .filter(Conversation.user_id == user.id)
            .delete(synchronize_session=False)
        )

        db.commit()

        logger.info(
            "User %s cleared their history: %s messages, "
            "%s essays, %s conversations",
            user.id,
            deleted_messages,
            deleted_artifacts,
            deleted_conversations,
        )

        return {
            "status": "success",
            "message": "Your history has been cleared.",
            "deleted": {
                "messages": deleted_messages,
                "artifacts": deleted_artifacts,
                "conversations": deleted_conversations,
            },
        }

    except Exception:
        db.rollback()

        logger.exception(
            "Failed to clear user history"
        )

        raise HTTPException(
            status_code=500,
            detail="Could not clear your history.",
        )

    finally:
        db.close()