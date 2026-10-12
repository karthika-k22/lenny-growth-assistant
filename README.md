\# The Lenny Growth Assistant



A full-stack AI assistant for exploring podcast transcripts, asking growth-related questions, and generating structured long-form essays.



\## Features



\- \*\*Conversational AI:\*\* Ask questions about indexed podcast transcripts.

\- \*\*Transcript retrieval:\*\* Searches transcript chunks and returns relevant source references.

\- \*\*Local LLM support:\*\* Uses Ollama with `qwen2.5:3b` for local inference.

\- \*\*Cloud model option:\*\* Supports OpenAI when API credentials and quota are available.

\- \*\*Conversation history:\*\* Saves conversations and messages in a local SQLite database.

\- \*\*Ship 30 for 30:\*\* Generates structured Markdown essays with a hook, narrative progression, and actionable takeaways.

\- \*\*Artifact history:\*\* Saves generated essays for later access.

\- \*\*Markdown preview:\*\* View generated content alongside its Markdown source.

\- \*\*Automated tests:\*\* Tests cover transcript retrieval and core API endpoints.



\## Technology Stack



\- Frontend: Next.js, React, TypeScript

\- Backend: Python, FastAPI

\- Retrieval: Keyword-based transcript search with term-frequency and inverse-document-frequency scoring

\- Local inference: Ollama

\- Database: SQLite with SQLAlchemy

\- Testing: pytest



\## Prerequisites



Install the following:



\- Python 3.13

\- Node.js and npm

\- Ollama

\- Git



Pull the local model:



```bash

ollama pull qwen2.5:3b

```



\## Run Locally



\### 1. Start the backend



From the project root, create and activate a virtual environment if you do not already have one, then install the project's Python dependencies.



Start the API:



```powershell

.\\.venv\\Scripts\\python.exe -m uvicorn backend.main:app --reload

```



Backend URL: `http://127.0.0.1:8000`



Interactive API documentation: `http://127.0.0.1:8000/docs`



\### 2. Start the frontend



Open another terminal:



```powershell

cd frontend

npm install

npm run dev

```



Open `http://localhost:3000`.



\### 3. Prepare transcript search



Place transcript text files (`.txt`) in:



```text

data/transcripts/

```



Build or refresh the transcript index using the project's `build\_index()` function from `backend.rag`.



\### 4. Configure providers



Select Ollama in the application to use the local model. Ensure Ollama is running and the configured model is available.



For cloud inference, configure a valid OpenAI API key using the application's supported environment configuration. Never commit API keys or other secrets to Git.



Local Ollama inference is the recommended option for testing without cloud API usage charges.



\## API Endpoints



| Method | Endpoint | Purpose |

|---|---|---|

| GET | `/health` | Health check |

| GET | `/api/models` | Available model/provider options |

| POST | `/api/chat` | Ask a question |

| POST | `/api/ship-30` | Generate a long-form essay |

| GET | `/api/conversations` | List saved conversations |

| GET | `/api/conversations/{session\_id}` | Retrieve a conversation |

| GET | `/api/artifacts` | List saved artifacts |



See `/docs` for the current request and response schemas.



\## Database and Persistence



Conversation messages and generated artifacts are stored in a local SQLite database:



```text

data/lenny\_assistant.db

```



This provides local persistence without requiring a separately hosted database service.



\## Tests



Run the complete automated test suite from the project root:



```powershell

.\\.venv\\Scripts\\python.exe -m pytest -v

```



The current tests cover:



\- Transcript retrieval and source metadata

\- Result limits

\- Empty and irrelevant queries

\- Health, model, conversation, and artifact endpoints



\## Known Limitations



\- Retrieval currently uses keyword-based scoring rather than semantic vector embeddings.

\- Answer quality depends on the available transcript corpus and selected model.

\- Cloud inference requires valid API credentials and available provider quota.

\- SQLite persistence is local to the machine unless the database is explicitly deployed or migrated.

\- The current automated tests do not replace manual end-to-end testing of the chat and essay-generation flows.

\- A public production deployment requires appropriate hosting, environment configuration, security review, and persistent storage.



\## Project Structure



```text

lenny-growth-assistant/

├── backend/

│   ├── main.py

│   ├── rag.py

│   └── database.py

├── frontend/

│   └── src/

│       └── app/

│           └── page.tsx

├── data/

│   └── transcripts/

├── tests/

│   ├── test\_api.py

│   └── test\_rag.py

├── README.md

└── .gitignore

```



\## Security Notes



\- Keep API keys out of source control.

\- Do not treat retrieved transcript text as trusted instructions.

\- Render generated HTML only in an appropriately isolated and sanitized viewer.

\- Do not expose local database files or private environment variables in a public deployment.



\## Development Status



This project is a local working prototype. Verify the configured provider, persistence, transcript sources, and artifact-rendering behavior before using it as a production service.



