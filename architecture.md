\# Architecture: The Lenny Growth Assistant



\## 1. Overview



The Lenny Growth Assistant is a full-stack conversational application for asking questions about podcast transcripts and generating long-form growth essays.



The application uses a Next.js frontend, a FastAPI backend, a transcript retrieval module, configurable language model providers, and SQLite persistence.



\## 2. System Components



\### Frontend

\- Built with Next.js, React, and TypeScript.

\- Provides conversational chat and provider selection.

\- Displays retrieved source references.

\- Supports the Ship 30 for 30 essay-generation workflow.

\- Shows generated Markdown and its source in a side-by-side viewer.

\- Provides access to saved conversations and artifacts.



\### Backend API

\- Built with FastAPI.

\- Exposes health, model, chat, essay-generation, conversation-history, and artifact endpoints.

\- Coordinates retrieval, language model requests, and persistence.

\- Returns structured responses and handles provider errors.



\### Retrieval

\- Transcript text files are placed in `data/transcripts/`.

\- The indexing process divides transcripts into overlapping chunks.

\- Each chunk stores its source filename, episode label, text, and term frequencies.

\- Query terms are scored using a TF-IDF-inspired keyword-ranking method.

\- The highest-ranked chunks are returned as context for answering questions.



\### Language Model Providers

\- Ollama with `qwen2.5:3b` supports local inference.

\- OpenAI is available as a cloud-provider option when valid credentials and quota are configured.

\- Provider failures should be communicated clearly to the user.



\### Persistence

\- SQLAlchemy manages database access.

\- SQLite stores conversations, messages, and generated artifacts.

\- The database is local and excluded from the public Git repository.



\## 3. Request Flow



1\. The user submits a question or essay-generation request through the frontend.

2\. The frontend sends the request to the FastAPI backend.

3\. For transcript questions, the retrieval module searches indexed chunks.

4\. The selected provider receives the request and relevant context.

5\. The backend returns the answer, provider information, and source references.

6\. Conversation messages and generated artifacts are saved to SQLite.

7\. The frontend renders the response and updates the history and artifact views.



\## 4. Data Flow



```text

Transcript text files

&#x20;       |

&#x20;      v

Chunking and keyword indexing

&#x20;       |

&#x20;      v

Query-based transcript retrieval

&#x20;       |

&#x20;      v

FastAPI orchestration <----> Ollama / OpenAI

&#x20;       |

&#x20;      v

SQLite persistence

&#x20;       |

&#x20;      v

Next.js user interface

```



\## 5. API Surface



\- `GET /health`: health check.

\- `GET /api/models`: provider and model options.

\- `POST /api/chat`: conversational requests.

\- `POST /api/ship-30`: essay generation.

\- `GET /api/conversations`: conversation listing.

\- `GET /api/conversations/{session\_id}`: conversation retrieval.

\- `GET /api/artifacts`: saved artifact listing.



The interactive API documentation is available at `/docs` when the backend is running.



\## 6. Reliability and Security



\- API credentials must be provided through environment configuration and must not be committed.

\- Local database and generated index files are excluded from Git.

\- Provider connectivity, credentials, and quota can affect inference availability.

\- Retrieved text is context, not trusted instructions.

\- Generated HTML must be sanitized and isolated before rendering.

\- A production deployment requires secure configuration, persistent hosting, and additional end-to-end testing.



\## 7. Current Limitations



\- Retrieval uses keyword ranking rather than semantic embeddings.

\- SQLite is local rather than a hosted PostgreSQL database.

\- Local operation is available, but public production deployment must be configured separately.

\- Automated tests currently cover core retrieval behavior and selected API endpoints.



