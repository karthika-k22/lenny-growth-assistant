# Lenny Growth Assistant

A full-stack AI growth assistant that helps users explore product growth concepts through conversational Q&A and generate long-form essays using a transcript-backed knowledge base.

**Live application:** https://lenny-growth-assistant-jet.vercel.app

## Features

- **AI Growth Chat:** Ask questions about product management, startups, growth, and related topics.
- **Transcript Retrieval:** Retrieves relevant passages from the configured transcript knowledge base to provide context for answers.
- **Ship 30:** Generate structured, long-form essays from a topic and intended audience.
- **User Authentication:** Register, log in, and authenticate using Google when configured.
- **Conversation History:** Save and revisit conversations.
- **Saved Essays:** Store generated essays as artifacts.
- **Data Isolation:** Authenticated users can access only their own conversations and artifacts.
- **Conversation Management:** Delete individual conversations while preserving saved essays.
- **Persistent Storage:** SQLAlchemy supports SQLite by default and PostgreSQL through database configuration.

## Tech Stack

| Layer | Technologies |
|---|---|
| Frontend | Next.js, React, TypeScript, Tailwind CSS |
| Backend | Python, FastAPI |
| Database | SQLAlchemy, SQLite, PostgreSQL support |
| AI Provider | Groq API |
| Model | `openai/gpt-oss-20b` |
| Retrieval | Transcript chunking and keyword-based ranking |
| Authentication | JWT, Argon2 password hashing, Google authentication |
| Testing | Pytest |

## Architecture

The application uses a Next.js frontend connected to a FastAPI backend.

For transcript-based questions, the backend retrieves relevant transcript chunks and supplies them as context to the language model. Conversation and artifact data are stored through SQLAlchemy.

See [architecture.md](architecture.md) for the system architecture and [design.md](design.md) for the interface and interaction principles.

## Project Structure

```text
lenny-growth-assistant/
├── backend/
│   ├── main.py
│   ├── database.py
│   └── rag.py
├── data/
│   └── transcripts/
├── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
├── tests/
├── architecture.md
├── design.md
├── requirements.txt
├── .env.example
└── README.md
```

## Getting Started

### Prerequisites

- Python
- Node.js and npm
- A Groq API key
- Git

### 1. Clone the repository

```bash
git clone https://github.com/karthika-k22/lenny-growth-assistant.git
cd lenny-growth-assistant
```

### 2. Set up the backend

Create and activate a virtual environment:

```bash
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root using `.env.example` as a reference.

Configure at least:

```env
GROQ_API_KEY=your_groq_api_key
JWT_SECRET_KEY=your_long_random_secret
```

### 3. Start the backend

```bash
python -m uvicorn backend.main:app --env-file .env --reload --port 8001
```

The backend runs at:

`http://localhost:8001`

Interactive API documentation:

`http://localhost:8001/docs`

### 4. Configure and start the frontend

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8001
```

Open a second terminal:

```bash
cd frontend
npm install
npm run dev
```

The frontend runs at:

`http://localhost:3000`

## Environment Variables

| Variable | Purpose |
|---|---|
| `GROQ_API_KEY` | API key used for Groq inference |
| `GROQ_MODEL` | Groq-supported model identifier |
| `JWT_SECRET_KEY` | Secret used to sign authentication tokens |
| `GOOGLE_CLIENT_ID` | Google authentication configuration |
| `DATABASE_URL` | Optional database connection URL |
| `NEXT_PUBLIC_API_URL` | Backend URL configured in the frontend |

If `DATABASE_URL` is not provided, the backend uses its default SQLite database configuration.

For PostgreSQL, provide a valid database connection URL through `DATABASE_URL`.

Never commit `.env`, `.env.local`, API keys, database credentials, or JWT secrets.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Backend health check |
| GET | `/api/models` | Model configuration status |
| POST | `/api/auth/register` | Register a user |
| POST | `/api/auth/login` | Authenticate a user |
| POST | `/api/auth/google` | Google authentication |
| GET | `/api/auth/me` | Retrieve the authenticated user |
| POST | `/api/chat` | Submit a chat message |
| POST | `/api/ship-30` | Generate a long-form essay |
| GET | `/api/conversations` | List conversations |
| GET | `/api/conversations/{session_id}` | Retrieve a conversation |
| DELETE | `/api/conversations/{session_id}` | Delete a conversation |
| GET | `/api/artifacts` | List saved artifacts |
| DELETE | `/api/history` | Clear conversation history |

## Testing

Run backend tests from the project root:

```bash
python -m pytest -v
```

If Pytest is not installed:

```bash
pip install pytest
```

Build the frontend:

```bash
cd frontend
npm run build
```

## Retrieval Approach

The application indexes transcript files stored in `data/transcripts/`.

The retrieval module:
1. Splits transcript content into manageable chunks.
2. Associates chunks with source and episode metadata.
3. Ranks relevant chunks using keyword-based scoring.
4. Selects the highest-ranked passages as context for the language model.

This is a lightweight retrieval approach rather than an embedding-based semantic search system. Answer relevance depends on the available transcript content and retrieval quality.

## Deployment

The application is deployed using:

- **Frontend:** Vercel
- **Backend:** Render

Production environment variables must be configured in the respective hosting dashboards. The frontend's `NEXT_PUBLIC_API_URL` must point to the deployed backend.

For reliable production persistence, configure a persistent database. A local SQLite file should not be assumed to survive deployments or ephemeral hosting storage.

## Current Limitations

- Retrieval uses keyword-based ranking rather than vector embeddings.
- Answer quality depends on the coverage and relevance of the available transcripts.
- AI responses depend on Groq service availability, API limits, and model behavior.
- Production database persistence and deployment configuration should be verified independently.
- Automated tests do not replace full end-to-end testing of the deployed application.

## License

No open-source license has been specified yet. All rights reserved unless a license is added to this repository.
