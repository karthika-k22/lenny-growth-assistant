"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

type Provider = "ollama" | "openai";
type Mode = "chat" | "essay";

type Source = {
  episode: string;
  source: string;
  score: number;
};

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Source[];
};

type EssayResult = {
  title: string;
  markdown: string;
  provider: string;
  timestamp: string;
};

type SavedConversation = {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count: number;
};

type SavedArtifact = {
  id: number;
  conversation_id: string;
  title: string;
  content: string;
  type: string;
  provider: string;
  created_at: string;
};

const buttonStyle = {
  padding: "10px 15px",
  borderRadius: 8,
  border: "1px solid #cbd5c9",
  cursor: "pointer",
  fontWeight: 600 as const,
};

export default function Home() {
  const [mode, setMode] = useState<Mode>("chat");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [sidebarWidth, setSidebarWidth] = useState(280);
  const [isResizing, setIsResizing] = useState(false);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [provider, setProvider] = useState<Provider>("ollama");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [topic, setTopic] = useState("");
  const [audience, setAudience] = useState(
    "product managers and startup founders"
  );
  const [essay, setEssay] = useState<EssayResult | null>(null);

  const [savedConversations, setSavedConversations] = useState<
    SavedConversation[]
  >([]);
  const [savedArtifacts, setSavedArtifacts] = useState<SavedArtifact[]>([]);
  const [sessionId, setSessionId] = useState("lenny-session");

  // History loading state
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyError, setHistoryError] = useState("");

  async function sendMessage(text?: string) {
    const prompt = (text ?? question).trim();
    if (!prompt || loading) return;

    const previousMessages = messages;
    const history = previousMessages.slice(-10).map((message) => ({
      role: message.role,
      content: message.content,
    }));

    setMessages((previous) => [
      ...previous,
      { role: "user", content: prompt },
    ]);
    setQuestion("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch("http://127.0.0.1:8000/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: prompt,
          session_id: sessionId,
          history,
          provider,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "The request failed. Please try again."
        );
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources ?? [],
        },
      ]);

      // Refresh history after a successful chat response
      void loadSavedHistory();
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not connect to the backend."
      );
    } finally {
      setLoading(false);
    }
  }

  async function generateEssay(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (topic.trim().length < 3 || loading) {
      setError("Enter an essay topic with at least 3 characters.");
      return;
    }

    setLoading(true);
    setError("");
    setEssay(null);

    try {
      const response = await fetch("http://127.0.0.1:8000/api/ship-30", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: topic.trim(),
          audience: audience.trim() || "general readers",
          provider,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Essay generation failed. Please try again."
        );
      }

      setEssay(data as EssayResult);
      void loadSavedHistory();
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : "Could not connect to the essay generator."
      );
    } finally {
      setLoading(false);
    }
  }

  async function loadSavedHistory() {
    setHistoryLoading(true);
    setHistoryError("");

    try {
      const [conversationResponse, artifactResponse] = await Promise.all([
        fetch("http://127.0.0.1:8000/api/conversations"),
        fetch("http://127.0.0.1:8000/api/artifacts"),
      ]);

      if (!conversationResponse.ok || !artifactResponse.ok) {
        throw new Error("Could not load saved history. Try refreshing.");
      }

      const conversationData = await conversationResponse.json();
      const artifactData = await artifactResponse.json();

      setSavedConversations(conversationData.conversations ?? []);
      setSavedArtifacts(artifactData.artifacts ?? []);
    } catch (e) {
      console.error("History loading failed:", e);
      setHistoryError(
        e instanceof Error
          ? e.message
          : "Could not connect to the backend."
      );
    } finally {
      setHistoryLoading(false);
    }
  }

  useEffect(() => {
    void loadSavedHistory();
  }, []);

  async function openSavedConversation(id: string) {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/conversations/${encodeURIComponent(id)}`
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not open conversation.");
      }

      setSessionId(data.id);
      setMessages(
        data.messages.map(
          (message: {
            role: "user" | "assistant";
            content: string;
          }) => ({
            role: message.role,
            content: message.content,
          })
        )
      );
      setMode("chat");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "Could not open conversation."
      );
    } finally {
      setLoading(false);
    }
  }

  function openSavedArtifact(artifact: SavedArtifact) {
    setEssay({
      title: artifact.title,
      markdown: artifact.content,
      provider: artifact.provider,
      timestamp: artifact.created_at,
    });
    setMode("essay");
    setError("");
  }

  async function copyEssay() {
    if (!essay) return;

    try {
      await navigator.clipboard.writeText(essay.markdown);
      setError("");
      window.alert("Essay Markdown copied to clipboard.");
    } catch {
      setError(
        "Clipboard access failed. Select and copy the Markdown manually."
      );
    }
  }

  function downloadEssay() {
    if (!essay) return;

    const blob = new Blob([essay.markdown], {
      type: "text/markdown;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "ship-30-for-30-essay.md";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  function newConversation() {
    setSessionId(crypto.randomUUID());
    setMessages([]);
    setQuestion("");
    setError("");
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        background: "#f6f7f3",
        color: "#242b25",
        fontFamily: "Arial, sans-serif",
      }}
    >
      <aside
        style={{
          width: sidebarCollapsed ? 0 : sidebarWidth,
          minWidth: sidebarCollapsed ? 0 : sidebarWidth,
          flexBasis: sidebarCollapsed ? 0 : 280,
          flexShrink: 0,
          padding: sidebarCollapsed ? 0 : 24,
          background: "#e9eee6",
          boxSizing: "border-box",
          overflow: "hidden",
          transition:
            "width 0.25s ease, min-width 0.25s ease, padding 0.25s ease",
        }}
      >
        <div
          style={{
            background: "#42684d",
            color: "white",
            borderRadius: 12,
            width: 44,
            height: 44,
            display: "grid",
            placeItems: "center",
            fontSize: 22,
            fontWeight: "bold",
          }}
        >
          L.
        </div>

        <h2>Lenny&apos;s Assistant</h2>
        <p style={{ color: "#657267", lineHeight: 1.6 }}>
          Your product and growth companion.
        </p>

        <label
          htmlFor="provider"
          style={{ display: "block", marginTop: 25, marginBottom: 8 }}
        >
          <strong>AI provider</strong>
        </label>

        <select
          id="provider"
          value={provider}
          onChange={(event) =>
            setProvider(event.target.value as Provider)
          }
          disabled={loading}
          style={{
            width: "100%",
            padding: 11,
            borderRadius: 8,
            border: "1px solid #cbd5c9",
            background: "white",
            color: "#242b25",
          }}
        >
          <option value="ollama">Ollama · Local AI</option>
          <option value="openai">OpenAI · Cloud AI</option>
        </select>

        <p style={{ color: "#42684d", fontSize: 13, lineHeight: 1.6 }}>
          {provider === "ollama"
            ? "● Local model: Qwen 2.5 3B"
            : "● Cloud model: GPT-4o mini"}
        </p>

        <button
          onClick={newConversation}
          style={{
            ...buttonStyle,
            marginTop: 15,
            background: "white",
          }}
        >
          + New conversation
        </button>

        <div style={{ marginTop: 24 }}>
          <h3 style={{ fontSize: 14 }}>Recent conversations</h3>

          {historyLoading ? (
            <p
              role="status"
              style={{
                fontSize: 13,
                color: "#42684d",
                padding: "10px 0",
                lineHeight: 1.6,
              }}
            >
              <span aria-hidden="true">⏳ </span>
              Loading conversation history...
            </p>
          ) : historyError ? (
            <div>
              <p
                role="alert"
                style={{
                  fontSize: 13,
                  color: "#b42318",
                  lineHeight: 1.6,
                }}
              >
                {historyError}
              </p>
              <button
                onClick={() => void loadSavedHistory()}
                style={{
                  ...buttonStyle,
                  background: "white",
                  width: "100%",
                }}
              >
                Try again
              </button>
            </div>
          ) : savedConversations.length === 0 ? (
            <p style={{ fontSize: 13, color: "#737b72" }}>
              No saved conversations yet.
            </p>
          ) : (
            savedConversations.map((item) => (
              <button
                key={item.id}
                onClick={() => void openSavedConversation(item.id)}
                disabled={loading}
                title={item.title}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: 10,
                  marginBottom: 6,
                  border: "1px solid #dce2d8",
                  borderRadius: 8,
                  background: "white",
                  color: "#344438",
                  cursor: "pointer",
                  overflowWrap: "anywhere",
                }}
              >
                <span>{item.title}</span>
                <span
                  style={{
                    display: "block",
                    fontSize: 11,
                    color: "#737b72",
                  }}
                >
                  {item.message_count} messages
                </span>
              </button>
            ))
          )}

          <h3 style={{ fontSize: 14, marginTop: 24 }}>Saved essays</h3>

          {historyLoading ? (
            <p style={{ fontSize: 13, color: "#737b72" }}>
              Loading saved essays...
            </p>
          ) : historyError ? (
            <p style={{ fontSize: 13, color: "#737b72" }}>
              Essays could not be loaded.
            </p>
          ) : savedArtifacts.length === 0 ? (
            <p style={{ fontSize: 13, color: "#737b72" }}>
              No saved essays yet.
            </p>
          ) : (
            savedArtifacts.map((item) => (
              <button
                key={item.id}
                onClick={() => openSavedArtifact(item)}
                style={{
                  display: "block",
                  width: "100%",
                  textAlign: "left",
                  padding: 10,
                  marginBottom: 6,
                  border: "1px solid #dce2d8",
                  borderRadius: 8,
                  background: "white",
                  color: "#344438",
                  cursor: "pointer",
                  overflowWrap: "anywhere",
                }}
              >
                {item.title}
              </button>
            ))
          )}

          <button
            onClick={() => void loadSavedHistory()}
            disabled={historyLoading}
            style={{
              ...buttonStyle,
              marginTop: 8,
              background: "white",
              width: "100%",
              opacity: historyLoading ? 0.6 : 1,
            }}
          >
            {historyLoading ? "Refreshing..." : "Refresh history"}
          </button>
        </div>

        <div
          style={{
            display: "grid",
            gap: 8,
            marginTop: 30,
          }}
        >
          <button
            onClick={() => {
              setMode("chat");
              setError("");
            }}
            style={{
              ...buttonStyle,
              textAlign: "left",
              background: mode === "chat" ? "#42684d" : "white",
              color: mode === "chat" ? "white" : "#344438",
            }}
          >
            Chat assistant
          </button>

          <button
            onClick={() => {
              setMode("essay");
              setError("");
            }}
            style={{
              ...buttonStyle,
              textAlign: "left",
              background: mode === "essay" ? "#42684d" : "white",
              color: mode === "essay" ? "white" : "#344438",
            }}
          >
            Ship 30 for 30
          </button>
        </div>

        <p style={{ marginTop: 25, fontSize: 12, color: "#737b72" }}>
          Essays are generated locally when Ollama is selected. OpenAI requires
          available API quota.
        </p>
      </aside>

      <button
        type="button"
        onClick={() => setSidebarCollapsed((collapsed) => !collapsed)}
        aria-label={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
        style={{
          position: "fixed",
          top: 18,
          left: sidebarCollapsed ? 12 : Math.max(8, sidebarWidth - 20),
          zIndex: 20,
          width: 36,
          height: 36,
          border: "1px solid #dce2d8",
          borderRadius: 8,
          background: "#ffffff",
          color: "#344438",
          cursor: "pointer",
          fontSize: 20,
          transition: "left 0.25s ease",
        }}
      >
        {sidebarCollapsed ? "☰" : "‹"}
      </button>

      {!sidebarCollapsed && (
        <div
          role="separator"
          aria-label="Resize sidebar"
          aria-orientation="vertical"
          title="Drag to resize sidebar"
          onPointerDown={(event) => {
            event.preventDefault();
            setIsResizing(true);
            event.currentTarget.setPointerCapture(event.pointerId);
          }}
          onPointerMove={(event) => {
            if (!isResizing) return;
            const newWidth = event.clientX;
            setSidebarWidth(Math.min(420, Math.max(200, newWidth)));
          }}
          onPointerUp={() => setIsResizing(false)}
          onPointerCancel={() => setIsResizing(false)}
          style={{
            position: "fixed",
            top: 0,
            bottom: 0,
            left: sidebarWidth - 3,
            width: 6,
            zIndex: 15,
            cursor: "col-resize",
            color: "#000000",
            touchAction: "none",
            background: isResizing ? "#42684d" : "transparent",
          }}
        />
      )}

      <section
        style={{
          flex: 1,
          minWidth: 0,
          padding: sidebarCollapsed ? "28px 5%" : "28px 4%",
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
          boxSizing: "border-box",
        }}
      >
        <header
          style={{
            borderBottom: "1px solid #dfe4dc",
            paddingBottom: 18,
          }}
        >
          <p
            style={{
              color: "#42684d",
              letterSpacing: 2,
              fontSize: 12,
              fontWeight: "bold",
            }}
          >
            LENNY&apos;S PODCAST
          </p>

          <h1 style={{ marginBottom: 8 }}>
            {mode === "chat"
              ? "The Lenny Growth Assistant"
              : "Ship 30 for 30 Essay Studio"}
          </h1>

          <p style={{ color: "#737b72", marginBottom: 0 }}>
            {mode === "chat"
              ? "Practical thinking for product, growth, and leadership."
              : "Turn a focused idea into a structured, publishable Markdown draft."}
          </p>
        </header>

        {mode === "chat" ? (
          <>
            <div style={{ flex: 1, padding: "20px 0" }}>
              {messages.length === 0 && (
                <>
                  <h2 style={{ fontSize: 30 }}>
                    What are you working on?
                  </h2>
                  <p style={{ color: "#737b72", lineHeight: 1.7 }}>
                    Ask about startup growth, product strategy, retention, or
                    experimentation. Choose your AI provider in the sidebar.
                  </p>

                  <div
                    style={{
                      display: "flex",
                      gap: 10,
                      flexWrap: "wrap",
                      marginTop: 20,
                    }}
                  >
                    {[
                      "How can I improve user retention?",
                      "How do I find product-market fit?",
                      "Suggest growth experiments",
                    ].map((item) => (
                      <button
                        key={item}
                        onClick={() => void sendMessage(item)}
                        disabled={loading}
                        style={{
                          ...buttonStyle,
                          background: "white",
                          color: "#344438",
                        }}
                      >
                        {item}
                      </button>
                    ))}
                  </div>
                </>
              )}

              {messages.map((message, index) => (
                <article
                  key={`${index}-${message.role}`}
                  style={{
                    margin: "18px 0",
                    marginLeft: message.role === "user" ? "12%" : 0,
                    background:
                      message.role === "user" ? "#e8eee5" : "white",
                    border: "1px solid #dce2d8",
                    padding: "18px 22px",
                    borderRadius: 12,
                    lineHeight: 1.75,
                    overflowWrap: "anywhere",
                  }}
                >
                  <strong style={{ color: "#42684d" }}>
                    {message.role === "user" ? "You" : "Lenny's Assistant"}
                  </strong>

                  <div style={{ marginTop: 8 }}>
                    {message.role === "assistant" ? (
                      <ReactMarkdown>{message.content}</ReactMarkdown>
                    ) : (
                      <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                        {message.content}
                      </p>
                    )}
                  </div>

                  {message.role === "assistant" &&
                    message.sources &&
                    message.sources.length > 0 && (
                      <div
                        style={{
                          marginTop: 18,
                          paddingTop: 12,
                          borderTop: "1px solid #e0e5dc",
                          fontSize: 13,
                          color: "#42684d",
                        }}
                      >
                        <strong>Sources</strong>
                        <ul style={{ paddingLeft: 20 }}>
                          {Array.from(
                            new Map(
                              message.sources.map((source) => [
                                source.source,
                                source,
                              ])
                            ).values()
                          ).map((source) => (
                            <li key={source.source}>
                              {source.episode} · {source.source}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                </article>
              ))}

              {loading && (
                <p style={{ color: "#42684d" }} role="status">
                  Thinking with{" "}
                  {provider === "ollama" ? "local Ollama" : "OpenAI"}...
                </p>
              )}
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                void sendMessage();
              }}
              style={{
                position: "sticky",
                bottom: 0,
                padding: 15,
                background: "#fff",
                border: "1px solid #dce2d8",
                borderRadius: 12,
              }}
            >
              <textarea
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                placeholder="Ask a question or follow up..."
                rows={3}
                style={{
                  width: "100%",
                  boxSizing: "border-box",
                  border: 0,
                  outline: 0,
                  resize: "vertical",
                  fontSize: 15,
                  fontFamily: "inherit",
                }}
              />

              <div style={{ textAlign: "right" }}>
                <button
                  type="submit"
                  disabled={loading || !question.trim()}
                  style={{
                    ...buttonStyle,
                    background: "#42684d",
                    color: "white",
                    border: 0,
                    opacity: loading || !question.trim() ? 0.6 : 1,
                  }}
                >
                  {loading ? "Thinking..." : "Send ↑"}
                </button>
              </div>
            </form>
          </>
        ) : (
          <>
            <form
              onSubmit={generateEssay}
              style={{
                margin: "22px 0",
                padding: 20,
                background: "white",
                border: "1px solid #dce2d8",
                borderRadius: 12,
                display: "grid",
                gap: 14,
              }}
            >
              <div>
                <label htmlFor="topic">
                  <strong>Essay topic</strong>
                </label>
                <input
                  id="topic"
                  value={topic}
                  onChange={(event) => setTopic(event.target.value)}
                  placeholder="e.g. Why retention matters more than growth hacks"
                  required
                  minLength={3}
                  maxLength={500}
                  style={{
                    display: "block",
                    width: "100%",
                    boxSizing: "border-box",
                    marginTop: 7,
                    padding: 12,
                    border: "1px solid #cbd5c9",
                    borderRadius: 8,
                    fontSize: 15,
                  }}
                />
              </div>

              <div>
                <label htmlFor="audience">
                  <strong>Target audience</strong>
                </label>
                <input
                  id="audience"
                  value={audience}
                  onChange={(event) => setAudience(event.target.value)}
                  maxLength={300}
                  style={{
                    display: "block",
                    width: "100%",
                    boxSizing: "border-box",
                    marginTop: 7,
                    padding: 12,
                    border: "1px solid #cbd5c9",
                    borderRadius: 8,
                    fontSize: 15,
                  }}
                />
              </div>

              <div>
                <button
                  type="submit"
                  disabled={loading || topic.trim().length < 3}
                  style={{
                    ...buttonStyle,
                    background: "#42684d",
                    color: "white",
                    border: 0,
                    opacity:
                      loading || topic.trim().length < 3 ? 0.6 : 1,
                  }}
                >
                  {loading
                    ? "Writing essay... this may take a minute"
                    : "Generate essay"}
                </button>
              </div>
            </form>

            {loading && (
              <p style={{ color: "#42684d" }} role="status">
                Ollama is drafting your essay. Long responses can take a little
                while.
              </p>
            )}

            {essay && (
              <>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    gap: 12,
                    flexWrap: "wrap",
                    marginBottom: 12,
                  }}
                >
                  <div>
                    <strong>{essay.title}</strong>
                    <p
                      style={{
                        color: "#737b72",
                        fontSize: 12,
                        margin: "5px 0",
                      }}
                    >
                      Generated by {essay.provider} ·{" "}
                      {new Date(essay.timestamp).toLocaleString()}
                    </p>
                  </div>

                  <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <button
                      onClick={() => void copyEssay()}
                      style={buttonStyle}
                    >
                      Copy Markdown
                    </button>
                    <button onClick={downloadEssay} style={buttonStyle}>
                      Download .md
                    </button>
                  </div>
                </div>

                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                    gap: 14,
                    alignItems: "start",
                  }}
                >
                  <section
                    style={{
                      minWidth: 0,
                      background: "white",
                      border: "1px solid #dce2d8",
                      borderRadius: 12,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        padding: 12,
                        background: "#000000",
                        color: "#ffffff",
                        borderBottom: "1px solid #dce2d8",
                        fontWeight: "bold",
                      }}
                    >
                      Artifact preview
                    </div>
                    <div
                      style={{
                        padding: 20,
                        maxHeight: "65vh",
                        overflowY: "auto",
                        overflowWrap: "anywhere",
                        lineHeight: 1.75,
                      }}
                    >
                      <ReactMarkdown>{essay.markdown}</ReactMarkdown>
                    </div>
                  </section>

                  <section
                    style={{
                      minWidth: 0,
                      background: "white",
                      border: "1px solid #dce2d8",
                      borderRadius: 12,
                      overflow: "hidden",
                    }}
                  >
                    <div
                      style={{
                        padding: 12,
                        background: "#e9eee6",
                        borderBottom: "1px solid #dce2d8",
                        fontWeight: "bold",
                      }}
                    >
                      Markdown source
                    </div>
                    <textarea
                      aria-label="Editable Markdown artifact"
                      value={essay.markdown}
                      onChange={(event) =>
                        setEssay({ ...essay, markdown: event.target.value })
                      }
                      spellCheck={false}
                      style={{
                        display: "block",
                        width: "100%",
                        boxSizing: "border-box",
                        minHeight: "65vh",
                        padding: 16,
                        border: 0,
                        resize: "vertical",
                        fontFamily: "Consolas, monospace",
                        fontSize: 13,
                        lineHeight: 1.6,
                      }}
                    />
                  </section>
                </div>
              </>
            )}
          </>
        )}

        {error && (
          <div
            role="alert"
            style={{
              color: "#b42318",
              background: "#fff1f0",
              padding: 12,
              borderRadius: 8,
              marginTop: 12,
            }}
          >
            {error}
            <button
              onClick={() => setError("")}
              style={{
                ...buttonStyle,
                marginLeft: 12,
                background: "white",
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        <p
          style={{
            color: "#92988f",
            fontSize: 11,
            textAlign: "center",
            marginTop: 12,
          }}
        >
          Transcript retrieval · AI-generated drafts need fact-checking ·
          Provider: {provider}
        </p>
      </section>
    </main>
  );
}