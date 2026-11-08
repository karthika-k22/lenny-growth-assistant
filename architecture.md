# Architecture: Lenny Growth Assistant

## 1. Overview

Lenny Growth Assistant is a full-stack AI application for exploring product growth concepts through conversational questions and generating long-form essays.

The system consists of a Next.js frontend, a FastAPI backend, a transcript retrieval module, a Groq-powered language model integration, and SQLAlchemy-based persistence.

## 2. System Components

### Frontend

- Built with Next.js, React, and TypeScript.
- Provides the conversational chat interface.
- Supports the Ship 30 essay-generation workflow.
- Renders assistant responses and generated Markdown.
- Provides access to conversation history and saved artifacts.
- Supports user authentication.

### Backend API

- Built with FastAPI.
- Handles authentication, chat requests, essay generation, and data management.
- Coordinates transcript retrieval and language model requests.
- Validates ownership of authenticated users' data.
- Persists conversations, messages, and artifacts through SQLAlchemy.

### Retrieval Module

- Transcript files are stored in `data/transcripts/`.
- Transcript content is divided into chunks.
- Chunks retain source and episode metadata.
- Queries are matched against indexed chunks using keyword-based ranking.
- The highest-ranked chunks are selected as context for the language model.

The current retrieval approach is lightweight and does not use vector embeddings.

### Language Model Integration

- Uses the Groq API for inference.
- The configured model is `openai/gpt-oss-20b`.
- The backend sends user prompts and relevant retrieved context to the model.
- API credentials remain on the backend and are not exposed to the frontend.
- Provider errors, missing configuration, and request failures are handled by the backend.

### Persistence

- SQLAlchemy manages database access.
- SQLite is used by default.
- PostgreSQL can be configured through `DATABASE_URL`.
- Stored data includes users, conversations, messages, and generated artifacts.
- Authenticated data access is scoped to the owning user.

## 3. Request Flow

### Conversational Chat

1. The user submits a question through the frontend.
2. The frontend sends the request to the FastAPI backend.
3. The backend validates the request and authentication context.
4. For authenticated conversations, existing history is loaded from the database.
5. The retrieval module searches indexed transcript chunks.
6. Relevant context and the conversation prompt are sent to Groq.
7. The backend returns the generated response.
8. Conversation messages are persisted.
9. The frontend displays the response.

### Essay Generation

1. The user submits an essay topic and relevant instructions.
2. The frontend sends the request to the essay-generation endpoint.
3. The backend processes the request and obtains a model response.
4. The generated essay is returned to the frontend.
5. Saved essays are stored as artifacts for later access.

## 4. Data Flow

```text
Transcript Files
       |
       v
Chunking and Keyword Indexing
       |
       v
Query-Based Retrieval
       |
       v
FastAPI Backend <----> Groq API
       |
       v
SQLAlchemy Persistence
       |
       v
SQLite / PostgreSQL
       |
       v
Next.js Frontend
```

## 5. API Surface

| Method | Endpoint | Responsibility |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/api/models` | Model configuration |
| POST | `/api/auth/register` | User registration |
| POST | `/api/auth/login` | User login |
| POST | `/api/auth/google` | Google authentication |
| GET | `/api/auth/me` | Current user |
| POST | `/api/chat` | Conversational AI |
| POST | `/api/ship-30` | Essay generation |
| GET | `/api/conversations` | Conversation listing |
| GET | `/api/conversations/{session_id}` | Conversation retrieval |
| DELETE | `/api/conversations/{session_id}` | Conversation deletion |
| GET | `/api/artifacts` | Saved artifact listing |
| DELETE | `/api/history` | History clearing |

Interactive API documentation is available at `/docs` when the backend is running.

## 6. Security and Data Integrity

- Secrets and API credentials are configured through environment variables.
- Passwords are hashed using Argon2.
- Authentication uses JWT tokens.
- Authenticated users can access only their own conversations and artifacts.
- Conversation ownership is validated before processing requests.
- Authenticated conversation history is loaded from the database rather than trusted from frontend-supplied history.
- Retrieved transcript content is treated as contextual data, not trusted instructions.
- Database records are associated with their owning users.

## 7. Deployment

The application uses a separately deployed frontend and backend.

- Frontend: Vercel
- Backend: Render

The frontend communicates with the backend through `NEXT_PUBLIC_API_URL`. Production secrets and database configuration are supplied through hosting environment variables.

A persistent database configuration is required for reliable production data retention.

## 8. Current Limitations

- Retrieval is based on keyword ranking rather than semantic embeddings.
- Retrieval quality depends on transcript coverage and query wording.
- Model availability and API limits depend on the external Groq service.
- Production database persistence must be verified against the actual hosting configuration.
- Automated tests cover selected backend behavior but do not constitute complete end-to-end coverage.
