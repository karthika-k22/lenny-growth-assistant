
"use client";

import { useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
};

type Conversation = {
  session_id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
};

type Artifact = {
  id?: number;
  title?: string;
  content?: string;
  artifact_type?: string;
  created_at?: string;
};

const buttonStyle: React.CSSProperties = {
  padding: "9px 12px",
  borderRadius: 8,
  border: "1px solid #333",
  background: "#181818",
  color: "#f4f4f5",
  cursor: "pointer",
  fontSize: 13,
};

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm Lenny's Growth Assistant. Ask me about product growth, retention, activation, experimentation, or startup strategy.",
    },
  ]);

  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("qwen2.5:3b");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [essayTopic, setEssayTopic] = useState("");
  const [essayLoading, setEssayLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "essay">("chat");

  const loadSavedHistory = useCallback(async () => {
    try {
      const [conversationResponse, artifactResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/conversations`),
        fetch(`${API_BASE_URL}/api/artifacts`),
      ]);

      if (conversationResponse.ok) {
        const data = await conversationResponse.json();
        setConversations(
          Array.isArray(data)
            ? data
            : data.conversations || data.items || [],
        );
      }

      if (artifactResponse.ok) {
        const data = await artifactResponse.json();
        setArtifacts(
          Array.isArray(data) ? data : data.artifacts || data.items || [],
        );
      }
    } catch {
      // History can be unavailable while the backend is offline.
    }
  }, []);

  useEffect(() => {
    void loadSavedHistory();
  }, [loadSavedHistory]);

  async function sendMessage() {
    const question = input.trim();

    if (!question || loading) return;

    const updatedMessages: Message[] = [
      ...messages,
      { role: "user", content: question },
    ];

    setMessages(updatedMessages);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: question,
          question,
          provider,
          model,
          session_id: sessionId || undefined,
          conversation_id: sessionId || undefined,
          history: messages.map((message) => ({
            role: message.role,
            content: message.content,
          })),
          messages: updatedMessages.map((message) => ({
            role: message.role,
            content: message.content,
          })),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || data.error || "The assistant could not answer.",
        );
      }

      const answer =
        data.answer ||
        data.response ||
        data.message ||
        data.content ||
        "I couldn't generate a response. Please try again.";

      const returnedSessionId =
        data.session_id || data.conversation_id || "";

      if (returnedSessionId) setSessionId(returnedSessionId);

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: answer,
          sources: data.sources || data.citations || [],
        },
      ]);

      await loadSavedHistory();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Something went wrong.";

      setError(message);
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content:
            "I couldn't complete that request. Check that the backend is running and your selected AI provider is available.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  async function generateEssay() {
    if (!essayTopic.trim() || essayLoading) return;

    setEssayLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/ship-30`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic: essayTopic.trim(),
          provider,
          model,
          session_id: sessionId || undefined,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || data.error || "Essay generation failed.",
        );
      }

      const essay =
        data.essay ||
        data.content ||
        data.response ||
        data.artifact?.content ||
        data.message ||
        "No essay was returned.";

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `# Ship 30 for 30 Essay\n\n${essay}`,
        },
      ]);

      if (data.session_id) setSessionId(data.session_id);

      await loadSavedHistory();
      setActiveTab("chat");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Essay generation failed.",
      );
    } finally {
      setEssayLoading(false);
    }
  }

  async function openConversation(id: string) {
    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/conversations/${encodeURIComponent(id)}`,
      );

      if (!response.ok) {
        throw new Error("Couldn't load this conversation.");
      }

      const data = await response.json();
      const storedMessages = data.messages || data.conversation?.messages || [];

      setSessionId(id);

      if (storedMessages.length) {
        setMessages(
          storedMessages.map(
            (message: {
              role?: string;
              content?: string;
              message?: string;
            }) => ({
              role:
                message.role === "user" ? "user" : "assistant",
              content: message.content || message.message || "",
            }),
          ),
        );
      } else {
        setMessages([
          {
            role: "assistant",
            content: "This conversation has no messages to display.",
          },
        ]);
      }

      setActiveTab("chat");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't open conversation.",
      );
    }
  }

  function startNewChat() {
    setSessionId("");
    setMessages([
      {
        role: "assistant",
        content:
          "New conversation started. What product-growth problem are we solving?",
      },
    ]);
    setError("");
    setActiveTab("chat");
  }

  async function copyText(text: string) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      setError("Clipboard access failed. Select the text and copy it manually.");
    }
  }

  function downloadText(title: string, content: string) {
    const blob = new Blob([content], {
      type: "text/markdown;charset=utf-8",
    });

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${title.replace(/[^a-z0-9-_]/gi, "_")}.md`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <main
      style={{
        minHeight: "100vh",
        display: "flex",
        background: "#0b0b0c",
        color: "#f4f4f5",
        fontFamily: "Arial, Helvetica, sans-serif",
      }}
    >
      {sidebarOpen && (
        <aside
          style={{
            width: 270,
            flexShrink: 0,
            borderRight: "1px solid #252525",
            padding: 18,
            display: "flex",
            flexDirection: "column",
            gap: 16,
            boxSizing: "border-box",
          }}
        >
          <div>
            <div style={{ fontSize: 20, fontWeight: 700 }}>
              Lenny&apos;s Assistant
            </div>
            <div style={{ color: "#999", fontSize: 12, marginTop: 5 }}>
              Product growth workspace
            </div>
          </div>

          <button
            style={{ ...buttonStyle, width: "100%" }}
            onClick={startNewChat}
          >
            + New conversation
          </button>

          <div>
            <div
              style={{
                color: "#999",
                fontSize: 12,
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: 1,
              }}
            >
              Conversations
            </div>

            <div style={{ display: "grid", gap: 6 }}>
              {conversations.length === 0 && (
                <div style={{ color: "#777", fontSize: 12 }}>
                  No saved conversations yet.
                </div>
              )}

              {conversations.map((conversation, index) => (
                <button
                  key={conversation.session_id || index}
                  onClick={() =>
                    conversation.session_id &&
                    void openConversation(conversation.session_id)
                  }
                  style={{
                    ...buttonStyle,
                    textAlign: "left",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    background:
                      sessionId === conversation.session_id
                        ? "#292929"
                        : "transparent",
                  }}
                >
                  {conversation.title ||
                    `Conversation ${index + 1}`}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div
              style={{
                color: "#999",
                fontSize: 12,
                marginBottom: 8,
                textTransform: "uppercase",
                letterSpacing: 1,
              }}
            >
              Generated artifacts
            </div>

            {artifacts.length === 0 ? (
              <div style={{ color: "#777", fontSize: 12 }}>
                Generated essays will appear here if saved by the backend.
              </div>
            ) : (
              <div style={{ display: "grid", gap: 6 }}>
                {artifacts.map((artifact, index) => (
                  <button
                    key={artifact.id ?? index}
                    style={{ ...buttonStyle, textAlign: "left" }}
                    onClick={() => {
                      if (artifact.content) {
                        setMessages((current) => [
                          ...current,
                          {
                            role: "assistant",
                            content: `# ${artifact.title || "Saved artifact"}\n\n${artifact.content}`,
                          },
                        ]);
                        setActiveTab("chat");
                      }
                    }}
                  >
                    {artifact.title || `Artifact ${index + 1}`}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div style={{ marginTop: "auto", color: "#777", fontSize: 11 }}>
            Lenny Growth Assistant
          </div>
        </aside>
      )}

      <section
        style={{
          minWidth: 0,
          flex: 1,
          display: "flex",
          flexDirection: "column",
          minHeight: "100vh",
        }}
      >
        <header
          style={{
            minHeight: 64,
            borderBottom: "1px solid #252525",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            padding: "12px 20px",
            boxSizing: "border-box",
            flexWrap: "wrap",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <button
              style={buttonStyle}
              onClick={() => setSidebarOpen((open) => !open)}
              aria-label="Toggle sidebar"
            >
              ☰
            </button>

            <div>
              <div style={{ fontWeight: 700 }}>Growth Assistant</div>
              <div style={{ color: "#888", fontSize: 12 }}>
                Ask. Explore. Build.
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <label htmlFor="provider" style={{ color: "#aaa", fontSize: 12 }}>
              Provider
            </label>

            <select
              id="provider"
              value={provider}
              onChange={(event) => {
                const value = event.target.value;
                setProvider(value);
                if (value === "ollama") setModel("qwen2.5:3b");
                if (value === "openai") setModel("gpt-4o-mini");
              }}
              style={{
                ...buttonStyle,
                maxWidth: 130,
              }}
            >
              <option value="ollama">Ollama</option>
              <option value="openai">OpenAI</option>
            </select>

            <label htmlFor="model" style={{ color: "#aaa", fontSize: 12 }}>
              Model
            </label>

            <input
              id="model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              style={{ ...buttonStyle, width: 125, boxSizing: "border-box" }}
            />
          </div>
        </header>

        <nav
          style={{
            display: "flex",
            gap: 8,
            padding: "12px 20px",
            borderBottom: "1px solid #202020",
          }}
        >
          <button
            style={{
              ...buttonStyle,
              background: activeTab === "chat" ? "#333" : "transparent",
            }}
            onClick={() => setActiveTab("chat")}
          >
            Chat
          </button>

          <button
            style={{
              ...buttonStyle,
              background: activeTab === "essay" ? "#333" : "transparent",
            }}
            onClick={() => setActiveTab("essay")}
          >
            Ship 30 for 30
          </button>
        </nav>

        {error && (
          <div
            role="alert"
            style={{
              margin: "12px 20px 0",
              padding: 12,
              border: "1px solid #743737",
              background: "#291515",
              borderRadius: 8,
              color: "#ffb7b7",
              fontSize: 13,
            }}
          >
            {error}
            <button
              onClick={() => setError("")}
              style={{
                ...buttonStyle,
                float: "right",
                padding: "2px 8px",
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        {activeTab === "chat" ? (
          <>
            <div
              style={{
                flex: 1,
                width: "100%",
                maxWidth: 900,
                boxSizing: "border-box",
                margin: "0 auto",
                padding: "24px 20px",
              }}
            >
              {messages.map((message, index) => (
                <article
                  key={`${index}-${message.role}`}
                  style={{
                    marginBottom: 22,
                    padding: 16,
                    border: "1px solid #252525",
                    borderRadius: 12,
                    background:
                      message.role === "user" ? "#171717" : "#101010",
                  }}
                >
                  <div
                    style={{
                      fontWeight: 700,
                      fontSize: 12,
                      color: message.role === "user" ? "#c4b5fd" : "#86efac",
                      marginBottom: 10,
                      textTransform: "uppercase",
                      letterSpacing: 0.8,
                    }}
                  >
                    {message.role === "user" ? "You" : "Lenny Assistant"}
                  </div>

                  <div
                    className="markdown-content"
                    style={{
                      fontSize: 14,
                      lineHeight: 1.75,
                      overflowWrap: "anywhere",
                    }}
                  >
                    <ReactMarkdown>{message.content}</ReactMarkdown>
                  </div>

                  {message.sources && message.sources.length > 0 && (
                    <div
                      style={{
                        marginTop: 14,
                        borderTop: "1px solid #333",
                        paddingTop: 10,
                        fontSize: 12,
                        color: "#aaa",
                      }}
                    >
                      <strong>Sources</strong>
                      <ul>
                        {message.sources.map((source, sourceIndex) => (
                          <li key={sourceIndex}>{source}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {message.role === "assistant" && index > 0 && (
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        marginTop: 14,
                        flexWrap: "wrap",
                      }}
                    >
                      <button
                        style={buttonStyle}
                        onClick={() => void copyText(message.content)}
                      >
                        Copy
                      </button>
                      <button
                        style={buttonStyle}
                        onClick={() =>
                          downloadText("lenny-response", message.content)
                        }
                      >
                        Download Markdown
                      </button>
                    </div>
                  )}
                </article>
              ))}

              {loading && (
                <div style={{ color: "#aaa", padding: 12 }}>
                  Thinking...
                </div>
              )}

              <div id="chat-bottom" />
            </div>

            <form
              onSubmit={(event) => {
                event.preventDefault();
                void sendMessage();
              }}
              style={{
                position: "sticky",
                bottom: 0,
                borderTop: "1px solid #252525",
                background: "#0b0b0c",
                padding: 16,
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  maxWidth: 900,
                  margin: "0 auto",
                  alignItems: "flex-end",
                }}
              >
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={(event) => {
                    if (
                      event.key === "Enter" &&
                      !event.shiftKey &&
                      !event.nativeEvent.isComposing
                    ) {
                      event.preventDefault();
                      void sendMessage();
                    }
                  }}
                  placeholder="Ask about activation, retention, growth loops..."
                  rows={2}
                  style={{
                    flex: 1,
                    resize: "vertical",
                    minHeight: 48,
                    maxHeight: 180,
                    padding: 12,
                    borderRadius: 10,
                    border: "1px solid #333",
                    background: "#151515",
                    color: "#f4f4f5",
                    fontSize: 14,
                    lineHeight: 1.5,
                    boxSizing: "border-box",
                  }}
                />

                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  style={{
                    ...buttonStyle,
                    padding: "13px 18px",
                    background:
                      loading || !input.trim() ? "#222" : "#f4f4f5",
                    color:
                      loading || !input.trim() ? "#888" : "#111",
                    fontWeight: 700,
                  }}
                >
                  {loading ? "..." : "Send"}
                </button>
              </div>

              <div
                style={{
                  maxWidth: 900,
                  margin: "8px auto 0",
                  color: "#777",
                  fontSize: 11,
                }}
              >
                Enter to send · Shift + Enter for a new line
              </div>
            </form>
          </>
        ) : (
          <div
            style={{
              width: "100%",
              maxWidth: 800,
              margin: "0 auto",
              padding: 24,
              boxSizing: "border-box",
            }}
          >
            <h1 style={{ fontSize: 25, marginBottom: 8 }}>
              Ship 30 for 30
            </h1>

            <p style={{ color: "#aaa", lineHeight: 1.6, fontSize: 14 }}>
              Generate a structured essay about a product-growth idea. Choose
              a specific topic, audience, or problem to make the result useful.
            </p>

            <label
              htmlFor="essay-topic"
              style={{
                display: "block",
                marginTop: 24,
                marginBottom: 8,
                fontSize: 13,
                fontWeight: 700,
              }}
            >
              What should the essay explore?
            </label>

            <textarea
              id="essay-topic"
              value={essayTopic}
              onChange={(event) => setEssayTopic(event.target.value)}
              placeholder="Example: How early-stage SaaS products can improve user activation..."
              rows={5}
              style={{
                width: "100%",
                boxSizing: "border-box",
                padding: 14,
                borderRadius: 10,
                border: "1px solid #333",
                background: "#151515",
                color: "#f4f4f5",
                fontSize: 14,
                lineHeight: 1.6,
              }}
            />

            <button
              disabled={essayLoading || !essayTopic.trim()}
              onClick={() => void generateEssay()}
              style={{
                ...buttonStyle,
                marginTop: 12,
                padding: "12px 18px",
                background:
                  essayLoading || !essayTopic.trim() ? "#222" : "#f4f4f5",
                color:
                  essayLoading || !essayTopic.trim() ? "#888" : "#111",
                fontWeight: 700,
              }}
            >
              {essayLoading ? "Generating..." : "Generate essay"}
            </button>

            <p style={{ color: "#777", fontSize: 12, marginTop: 12 }}>
              Your generated essay will appear in the Chat tab.
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
