
import os
import logging
from datetime import datetime, timezone
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.rag import search_transcripts


from backend.database import (
    SessionLocal,
    Conversation,
    ChatMessage,
    GeneratedArtifact,
)

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lenny-assistant")


def save_chat_exchange(
    session_id: str,
    user_message: str,
    assistant_message: str,
    provider: str,
):
    """Persist a user question and its assistant response."""
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, session_id)

        if conversation is None:
            conversation = Conversation(
                id=session_id,
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
        logger.exception("Failed to save chat exchange")
        raise
    finally:
        db.close()


def save_generated_artifact(
    title: str,
    content: str,
    provider: str,
):
    """Persist a generated essay."""
    db = SessionLocal()
    session_id = "essay-session"

    try:
        conversation = db.get(Conversation, session_id)

        if conversation is None:
            conversation = Conversation(
                id=session_id,
                title="Ship 30 for 30 Essays",
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
        logger.exception("Failed to save generated artifact")
        raise
    finally:
        db.close()

app = FastAPI(
    title="The Lenny Growth Assistant",
    description="An AI assistant for product and growth questions.",
    version="0.3.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5:3b")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=10000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    session_id: str = "default"
    history: list[Message] = Field(default_factory=list, max_length=20)
    provider: Literal["ollama", "openai"] = "ollama"


class ChatResponse(BaseModel):
    answer: str
    session_id: str
    provider: str
    timestamp: str
    sources: list[dict] = Field(default_factory=list)


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
                "provider": "openai",
                "model": OPENAI_MODEL,
                "local": False,
                "configured": bool(os.getenv("OPENAI_API_KEY")),
            },
        ]
    }


def build_instructions(sources: list[dict]) -> str:
    instructions = (
        "You are The Lenny Growth Assistant. Help with product management, "
        "startups, user growth, experimentation, and leadership. "
        "Answer follow-up questions using the conversation history. "
        "Be practical, specific, and concise. Use Markdown headings and bullets. "
        "Use the supplied podcast transcript excerpts when relevant. "
        "Cite transcript evidence using the exact source filename, "
        "for example [Source: product_growth.txt]. Never invent citations. "
        "Only claim that something was said in a podcast when the excerpts "
        "support that claim. If no excerpt supports the answer, say so clearly "
        "and distinguish general knowledge from transcript evidence. "
        "Do not invent statistics, quotes, episode details, or speaker claims."
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
            "No matching podcast transcript excerpts were found. "
            "Do not claim that the podcast supports your answer."
        )

    return (
        instructions
        + "\n\nPODCAST TRANSCRIPT SEARCH RESULTS:\n"
        + source_text
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    sources = search_transcripts(request.message, top_k=4)
    instructions = build_instructions(sources)

    conversation = []
    for item in request.history[-10:]:
        conversation.append(
            {
                "role": item.role,
                "content": item.content,
            }
        )

    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            if request.provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")

                if not api_key:
                    raise HTTPException(
                        status_code=503,
                        detail=(
                            "OpenAI is not configured. Add OPENAI_API_KEY "
                            "to your local .env file to enable it."
                        ),
                    )

                messages = [
                    {"role": "system", "content": instructions},
                    *conversation,
                    {"role": "user", "content": request.message},
                ]

                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENAI_MODEL,
                        "messages": messages,
                        "max_tokens": 450,
                    },
                )
                response.raise_for_status()
                data = response.json()

                answer = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    or ""
                ).strip()

                provider_name = f"openai/{OPENAI_MODEL}"

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
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": prompt,
                        "stream": False,
                        "keep_alive": "10m",
                        "options": {"num_predict": 450},
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

        try:
            save_chat_exchange(
                session_id=request.session_id,
                user_message=request.message,
                assistant_message=answer,
                provider=provider_name,
            )
        except Exception:
            logger.exception(
                "Chat response succeeded but persistence failed"
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
        logger.exception("Could not connect to the selected AI provider")
        raise HTTPException(
            status_code=503,
            detail=(
                "Could not connect to the selected AI provider. "
                "Check that the service is running and reachable."
            ),
        )

    except httpx.TimeoutException:
        logger.exception("AI provider request timed out")
        raise HTTPException(
            status_code=504,
            detail="The model took too long to respond. Please retry.",
        )

    except httpx.HTTPStatusError as exc:
        logger.error(
            "AI provider returned HTTP %s",
            exc.response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail=(
                "The selected AI provider returned an error "
                f"(HTTP {exc.response.status_code}). Check its configuration."
            ),
        )

    except (ValueError, KeyError, IndexError):
        logger.exception("Could not parse the model response")
        raise HTTPException(
            status_code=502,
            detail="The selected AI provider returned an invalid response.",
        )


class EssayRequest(BaseModel):
    topic: str = Field(min_length=3, max_length=500)
    audience: str = Field(default="product managers and startup founders", max_length=300)
    provider: Literal["ollama", "openai"] = "ollama"


class EssayResponse(BaseModel):
    title: str
    markdown: str
    provider: str
    timestamp: str


@app.post("/api/ship-30")
async def generate_ship_30(request: EssayRequest):
    """Generate a structured Ship 30 for 30-style essay."""


    instructions = f"""
You are an experienced essay writer creating a Ship 30 for 30-style essay.

TOPIC: {request.topic}
TARGET AUDIENCE: {request.audience}

Write approximately 1,250 words. Aim for 1,100 to 1,400 words.

STRUCTURE:
1. Start with a compelling, concrete hook that makes the reader care.
2. Introduce one clear central argument.
3. Develop a logical narrative with useful Markdown headings.
4. Use short paragraphs, specific examples, and practical explanations.
5. Explain why the ideas matter to the target audience.
6. End with one specific, actionable takeaway.

FACTUAL ACCURACY:
- Never invent statistics, studies, citations, quotations, or research findings.
- Do not attribute claims to real companies or people unless you can
  reliably support those claims.
- Do not imply this essay is based on podcast transcripts.
- Use hypothetical examples only when clearly identified as hypothetical.
- Prefer clear reasoning and practical guidance over unsupported facts.
- Avoid repetitive introductions and conclusions.

OUTPUT:
Return Markdown only.
Begin with a single # title.
Use ## headings for major sections.
Finish with a clearly labeled "Actionable Takeaway" section.
"""

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            if request.provider == "openai":
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise HTTPException(
                        status_code=503,
                        detail="OpenAI is not configured. Use Ollama or configure an API key.",
                    )

                response = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": OPENAI_MODEL,
                        "messages": [
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": "Write the essay now."},
                        ],
                        "max_tokens": 3000,
                    },
                )
                response.raise_for_status()
                data = response.json()
                markdown = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    or ""
                ).strip()
                provider_name = f"openai/{OPENAI_MODEL}"

            else:
                response = await client.post(
                    f"{OLLAMA_URL.rstrip('/')}/api/generate",
                    json={
                        "model": OLLAMA_MODEL,
                        "prompt": instructions + "\n\nWrite the essay now:",
                        "stream": False,
                        "keep_alive": "10m",
                        "options": {"num_predict": 3000},
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
                line.lstrip("# ").strip()
                for line in markdown.splitlines()
                if line.startswith("# ")
            ),
            request.topic,
        )

        try:
            save_generated_artifact(
                title=title,
                content=markdown,
                provider=provider_name,
            )
        except Exception:
            logger.exception(
                "Essay generation succeeded but persistence failed"
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
        logger.exception("Essay generation timed out")
        raise HTTPException(
            status_code=504,
            detail="Essay generation timed out. Try a shorter topic or retry.",
        )
    except httpx.ConnectError:
        logger.exception("Could not connect to the selected provider")
        raise HTTPException(
            status_code=503,
            detail="Could not connect to the selected AI provider. Check that it is running.",
        )
    except httpx.HTTPStatusError as exc:
        logger.error("Essay provider returned HTTP %s", exc.response.status_code)
        raise HTTPException(
            status_code=502,
            detail=f"The AI provider returned HTTP {exc.response.status_code}.",
        )


@app.get("/api/conversations")
async def list_conversations():
    """Return saved conversations, newest activity first."""
    db = SessionLocal()
    try:
        conversations = (
            db.query(Conversation)
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
        logger.exception("Failed to list conversations")
        raise HTTPException(
            status_code=500,
            detail="Could not load conversation history.",
        )
    finally:
        db.close()


@app.get("/api/conversations/{session_id}")
async def get_conversation(session_id: str):
    """Return messages belonging to one saved conversation."""
    db = SessionLocal()
    try:
        conversation = db.get(Conversation, session_id)

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
        logger.exception("Failed to load conversation")
        raise HTTPException(
            status_code=500,
            detail="Could not load this conversation.",
        )
    finally:
        db.close()


@app.get("/api/artifacts")
async def list_artifacts():
    """Return saved Ship 30 for 30 essays."""
    db = SessionLocal()
    try:
        artifacts = (
            db.query(GeneratedArtifact)
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
        logger.exception("Failed to list saved essays")
        raise HTTPException(
            status_code=500,
            detail="Could not load saved essays.",
        )
    finally:
        db.close()

