
"use client";

import {
  FormEvent,
  KeyboardEvent,
  useCallback,
  useEffect,
  useState,
} from "react";
import ReactMarkdown from "react-markdown";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const WELCOME_MESSAGE =
  "Hi! I'm Lenny's Growth Assistant. Ask me about product growth, retention, activation, experimentation, or startup strategy.";

const TOKEN_KEY = "lenny_access_token";

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: Array<string | { source?: string; episode?: string }>;
};

type Conversation = {
  id: string;
  session_id: string;
  title?: string;
  created_at?: string;
  updated_at?: string;
  message_count?: number;
};

type Artifact = {
  id?: number;
  conversation_id?: string;
  title?: string;
  content?: string;
  type?: string;
  artifact_type?: string;
  provider?: string;
  created_at?: string;
};

type User = {
  id: number;
  email: string;
};

const newSessionId = () => {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `session-${Date.now()}-${Math.random().toString(16).slice(2)}`;
};

const styles: Record<string, React.CSSProperties> = {
  page: {
    minHeight: "100vh",
    display: "flex",
    background: "#07110d",
    color: "#e8f3ec",
    fontFamily: "Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, sans-serif",
  },
  sidebar: {
    width: 286,
    flexShrink: 0,
    display: "flex",
    flexDirection: "column",
    gap: 20,
    padding: 20,
    boxSizing: "border-box",
    background: "#0a1711",
    borderRight: "1px solid #183b29",
    minHeight: "100vh",
  },
  brand: { fontSize: 20, fontWeight: 800, letterSpacing: "-0.5px" },
  muted: { color: "#8da99a" },
  primaryButton: {
    border: "1px solid #28784c",
    background: "linear-gradient(135deg, #176b3c, #0e482b)",
    color: "#effff4",
    borderRadius: 10,
    padding: "11px 14px",
    fontWeight: 700,
    cursor: "pointer",
  },
  secondaryButton: {
    border: "1px solid #28513a",
    background: "#102219",
    color: "#dcefe3",
    borderRadius: 9,
    padding: "9px 12px",
    cursor: "pointer",
  },
  main: {
    minWidth: 0,
    flex: 1,
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
    background:
      "radial-gradient(ellipse at 50% -25%, rgba(25,110,63,.18), transparent 55%), #07110d",
  },
  header: {
    minHeight: 76,
    padding: "14px 24px",
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14,
    flexWrap: "wrap",
    borderBottom: "1px solid #183b29",
    background: "rgba(8, 22, 15, .88)",
  },
  content: {
    width: "100%",
    maxWidth: 980,
    boxSizing: "border-box",
    margin: "0 auto",
    padding: "28px 22px",
    flex: 1,
  },
  card: {
    border: "1px solid #1c4931",
    borderRadius: 14,
    background: "linear-gradient(145deg, rgba(15,35,24,.96), rgba(9,22,15,.96))",
    padding: 18,
    marginBottom: 16,
    boxShadow: "0 10px 30px rgba(0,0,0,.12)",
  },
  input: {
    width: "100%",
    boxSizing: "border-box",
    border: "1px solid #28513a",
    borderRadius: 11,
    background: "#0b1a12",
    color: "#e8f3ec",
    padding: 13,
    fontSize: 14,
    outlineColor: "#42bd75",
  },
  label: {
    color: "#9db9a7",
    fontSize: 11,
    fontWeight: 800,
    letterSpacing: "1.2px",
    textTransform: "uppercase",
  },
  overlay: {
    position: "fixed",
    inset: 0,
    zIndex: 20,
    background: "rgba(0,0,0,.72)",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    padding: 18,
  },
  modal: {
    width: "100%",
    maxWidth: 420,
    border: "1px solid #28513a",
    borderRadius: 16,
    background: "#0a1711",
    padding: 24,
    boxShadow: "0 20px 70px rgba(0,0,0,.45)",
  },
};

function SectionLabel({ children }: { children: React.ReactNode }) {
  return <div style={{ ...styles.label, marginBottom: 9 }}>{children}</div>;
}

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([
    { role: "assistant", content: WELCOME_MESSAGE },
  ]);
  const [input, setInput] = useState("");
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("qwen2.5:3b");
  const [loading, setLoading] = useState(false);
  const [clearingHistory, setClearingHistory] = useState(false);
  const [error, setError] = useState("");
  const [sessionId, setSessionId] = useState("");
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [artifacts, setArtifacts] = useState<Artifact[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [essayTopic, setEssayTopic] = useState("");
  const [essayLoading, setEssayLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<"chat" | "essay">("chat");

  const [token, setToken] = useState("");
  const [user, setUser] = useState<User | null>(null);
  const [authReady, setAuthReady] = useState(false);
  const [authOpen, setAuthOpen] = useState(false);
  const [authMode, setAuthMode] = useState<"login" | "register">("login");
  const [authEmail, setAuthEmail] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authLoading, setAuthLoading] = useState(false);
  const [authError, setAuthError] = useState("");

  const authHeaders = useCallback(
    (extra: Record<string, string> = {}) => ({
      ...extra,
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    }),
    [token],
  );

  const loadSavedHistory = useCallback(async () => {
    if (!token) {
      setConversations([]);
      setArtifacts([]);
      return;
    }

    try {
      const headers = authHeaders();
      const [conversationResponse, artifactResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/conversations`, { headers }),
        fetch(`${API_BASE_URL}/api/artifacts`, { headers }),
      ]);

      if (conversationResponse.status === 401 || artifactResponse.status === 401) {
        logout();
        return;
      }

      if (conversationResponse.ok) {
        const data = await conversationResponse.json();
        const items = Array.isArray(data)
          ? data
          : data.conversations || data.items || [];

        setConversations(
          items
            .map((item: any) => {
              const id = String(item.id || item.session_id || "");
              return { ...item, id, session_id: id };
            })
            .filter((item: Conversation) => item.id),
        );
      }

      if (artifactResponse.ok) {
        const data = await artifactResponse.json();
        setArtifacts(
          Array.isArray(data) ? data : data.artifacts || data.items || [],
        );
      }
    } catch {
      setError("Conversation history is temporarily unavailable.");
    }
  }, [token, authHeaders]);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      const savedToken = sessionStorage.getItem(TOKEN_KEY);

      if (!savedToken) {
        if (!cancelled) setAuthReady(true);
        return;
      }

      try {
        const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
          headers: { Authorization: `Bearer ${savedToken}` },
        });

        if (!response.ok) {
          sessionStorage.removeItem(TOKEN_KEY);
          if (!cancelled) setAuthReady(true);
          return;
        }

        const account = await response.json();

        if (!cancelled) {
          setToken(savedToken);
          setUser(account);
        }
      } catch {
        if (!cancelled) {
          setError("Could not verify your saved login. Please check your connection.");
        }
      } finally {
        if (!cancelled) setAuthReady(true);
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (authReady && token) {
      void loadSavedHistory();
    }
  }, [authReady, token, loadSavedHistory]);

  function startNewChat() {
    setSessionId(newSessionId());
    setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    setInput("");
    setError("");
    setEssayTopic("");
    setActiveTab("chat");
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    setToken("");
    setUser(null);
    setConversations([]);
    setArtifacts([]);
    setSessionId(newSessionId());
    setMessages([{ role: "assistant", content: WELCOME_MESSAGE }]);
    setInput("");
    setEssayTopic("");
    setActiveTab("chat");
    setAuthOpen(false);
    setError("");
  }

  async function submitAuth(event: FormEvent) {
    event.preventDefault();

    if (authLoading) return;

    setAuthLoading(true);
    setAuthError("");

    try {
      const endpoint =
        authMode === "register"
          ? "/api/auth/register"
          : "/api/auth/login";

      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: authEmail.trim(),
          password: authPassword,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || "Authentication failed. Please try again.",
        );
      }

      if (!data.access_token || !data.user) {
        throw new Error("The server returned an invalid login response.");
      }

      sessionStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
      setUser(data.user);
      setAuthOpen(false);
      setAuthEmail("");
      setAuthPassword("");
      setAuthError("");

      // Guest conversations are not automatically transferred.
      startNewChat();
      setConversations([]);
      setArtifacts([]);
    } catch (err) {
      setAuthError(
        err instanceof Error ? err.message : "Authentication failed.",
      );
    } finally {
      setAuthLoading(false);
    }
  }

  async function clearHistory() {
    if (!user || !token) {
      setError("Sign in to clear your saved history.");
      return;
    }

    const confirmed = window.confirm(
      "This will permanently delete your saved conversations, messages, and essays from YOUR account only. Continue?",
    );

    if (!confirmed || clearingHistory) return;

    setClearingHistory(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/history`, {
        method: "DELETE",
        headers: authHeaders(),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not clear your history.");
      }

      setConversations([]);
      setArtifacts([]);
      startNewChat();

      alert("Your saved history has been cleared.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not clear history.");
    } finally {
      setClearingHistory(false);
    }
  }

  async function sendMessage(event?: FormEvent) {
    event?.preventDefault();

    const question = input.trim();
    if (!question || loading) return;

    const activeSessionId = sessionId || newSessionId();
    setSessionId(activeSessionId);

    const history = messages.filter(
      (message, index) =>
        !(index === 0 && message.content === WELCOME_MESSAGE),
    );

    setMessages((current) => [
      ...current,
      { role: "user", content: question },
    ]);
    setInput("");
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          message: question,
          provider,
          model,
          session_id: activeSessionId,
          history: history.map(({ role, content }) => ({ role, content })),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || data.error || "The assistant could not answer.",
        );
      }

      const answer = String(
        data.answer || data.response || data.content || "",
      ).trim();

      if (!answer) {
        throw new Error("The assistant returned an empty response.");
      }

      if (data.session_id) setSessionId(data.session_id);

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: answer,
          sources: Array.isArray(data.sources) ? data.sources : [],
        },
      ]);

      if (token) await loadSavedHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  async function generateEssay() {
    const topic = essayTopic.trim();
    if (!topic || essayLoading) return;

    const activeSessionId = sessionId || newSessionId();
    setSessionId(activeSessionId);
    setEssayLoading(true);
    setError("");

    try {
      const response = await fetch(`${API_BASE_URL}/api/ship-30`, {
        method: "POST",
        headers: authHeaders({ "Content-Type": "application/json" }),
        body: JSON.stringify({
          topic,
          provider,
          session_id: activeSessionId,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.detail || data.error || "Essay generation failed.",
        );
      }

      const essay = String(
        data.markdown ||
          data.essay ||
          data.content ||
          data.response ||
          data.artifact?.content ||
          "",
      ).trim();

      if (!essay) {
        throw new Error(
          "The essay generator returned an empty response. Please try again.",
        );
      }

      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: essay.startsWith("#")
            ? essay
            : `# ${data.title || topic}\n\n${essay}`,
        },
      ]);

      if (data.session_id) setSessionId(data.session_id);

      setActiveTab("chat");
      setEssayTopic("");

      if (token) await loadSavedHistory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Essay generation failed.");
    } finally {
      setEssayLoading(false);
    }
  }

  async function openConversation(id: string) {
    if (!token) return;

    setError("");

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/conversations/${encodeURIComponent(id)}`,
        { headers: authHeaders() },
      );

      if (!response.ok) {
        throw new Error("Couldn't load this conversation.");
      }

      const data = await response.json();
      const storedMessages = data.messages || data.conversation?.messages || [];

      setSessionId(id);

      setMessages(
        storedMessages.length
          ? storedMessages.map((message: any) => ({
              role: message.role === "user" ? "user" : "assistant",
              content: message.content || message.message || "",
            }))
          : [
              {
                role: "assistant",
                content: "This conversation has no messages to display.",
              },
            ],
      );

      setActiveTab("chat");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Couldn't open conversation.",
      );
    }
  }

  function openArtifact(artifact: Artifact) {
    if (!artifact.content) return;

    setMessages([
      {
        role: "assistant",
        content: `# ${artifact.title || "Saved essay"}\n\n${artifact.content}`,
      },
    ]);

    setSessionId(artifact.conversation_id || "");
    setActiveTab("chat");
    setError("");
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

  function handleComposerKeyDown(
    event: KeyboardEvent<HTMLTextAreaElement>,
  ) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      void sendMessage();
    }
  }

  return (
    <main style={styles.page}>
      {authOpen && (
        <div style={styles.overlay}>
          <div style={styles.modal}>
            <div style={{ ...styles.brand, marginBottom: 8 }}>
              {authMode === "login" ? "Welcome back" : "Create your account"}
            </div>

            <p style={{ ...styles.muted, fontSize: 13, marginBottom: 22 }}>
              {authMode === "login"
                ? "Sign in to access your private conversations and essays."
                : "Create an account to save your conversations and essays."}
            </p>

            <form onSubmit={(event) => void submitAuth(event)}>
              <label htmlFor="auth-email" style={styles.label}>
                Email address
              </label>

              <input
                id="auth-email"
                type="email"
                autoComplete="email"
                required
                value={authEmail}
                onChange={(event) => setAuthEmail(event.target.value)}
                placeholder="you@example.com"
                style={{ ...styles.input, marginTop: 8, marginBottom: 16 }}
              />

              <label htmlFor="auth-password" style={styles.label}>
                Password
              </label>

              <input
                id="auth-password"
                type="password"
                autoComplete={
                  authMode === "login" ? "current-password" : "new-password"
                }
                minLength={authMode === "register" ? 8 : 1}
                maxLength={128}
                required
                value={authPassword}
                onChange={(event) => setAuthPassword(event.target.value)}
                placeholder={
                  authMode === "register"
                    ? "At least 8 characters"
                    : "Your password"
                }
                style={{ ...styles.input, marginTop: 8, marginBottom: 16 }}
              />

              {authError && (
                <div
                  role="alert"
                  style={{
                    color: "#ffcaca",
                    background: "#2b1717",
                    border: "1px solid #9b4848",
                    borderRadius: 9,
                    padding: 10,
                    fontSize: 13,
                    marginBottom: 14,
                  }}
                >
                  {authError}
                </div>
              )}

              <button
                type="submit"
                disabled={authLoading}
                style={{
                  ...styles.primaryButton,
                  width: "100%",
                  opacity: authLoading ? 0.6 : 1,
                }}
              >
                {authLoading
                  ? "Please wait..."
                  : authMode === "login"
                    ? "Sign in"
                    : "Create account"}
              </button>
            </form>

            <div
              style={{
                textAlign: "center",
                fontSize: 13,
                color: "#9db9a7",
                marginTop: 18,
              }}
            >
              {authMode === "login"
                ? "Don't have an account?"
                : "Already have an account?"}{" "}
              <button
                type="button"
                onClick={() => {
                  setAuthMode(authMode === "login" ? "register" : "login");
                  setAuthError("");
                }}
                style={{
                  border: 0,
                  background: "transparent",
                  color: "#62df96",
                  cursor: "pointer",
                  fontWeight: 700,
                }}
              >
                {authMode === "login" ? "Sign up" : "Sign in"}
              </button>
            </div>

            <button
              type="button"
              onClick={() => {
                setAuthOpen(false);
                setAuthError("");
              }}
              style={{
                ...styles.secondaryButton,
                width: "100%",
                marginTop: 18,
              }}
            >
              Continue as guest
            </button>
          </div>
        </div>
      )}

      {sidebarOpen && (
        <aside style={styles.sidebar}>
          <div>
            <div style={styles.brand}>
              Lenny<span style={{ color: "#55d98a" }}>&apos;s</span> Assistant
            </div>

            <div style={{ ...styles.muted, fontSize: 12, marginTop: 5 }}>
              Product growth workspace
            </div>
          </div>

          <button
            style={{ ...styles.primaryButton, width: "100%" }}
            onClick={startNewChat}
          >
            + New conversation
          </button>

          <section>
            <SectionLabel>Conversations</SectionLabel>

            <div style={{ display: "grid", gap: 7 }}>
              {conversations.length === 0 && (
                <div style={{ ...styles.muted, fontSize: 12 }}>
                  {user
                    ? "No saved conversations yet."
                    : "Sign in to save conversations."}
                </div>
              )}

              {conversations.map((conversation, index) => (
                <button
                  key={conversation.id}
                  onClick={() => void openConversation(conversation.id)}
                  title={conversation.title || `Conversation ${index + 1}`}
                  style={{
                    ...styles.secondaryButton,
                    textAlign: "left",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    whiteSpace: "nowrap",
                    background:
                      sessionId === conversation.id ? "#17452c" : "#0d1d14",
                    borderColor:
                      sessionId === conversation.id ? "#3a9e62" : "#244632",
                  }}
                >
                  {conversation.title || `Conversation ${index + 1}`}
                </button>
              ))}
            </div>
          </section>

          <section>
            <SectionLabel>Generated essays</SectionLabel>

            <div style={{ display: "grid", gap: 7 }}>
              {artifacts.length === 0 && (
                <div style={{ ...styles.muted, fontSize: 12 }}>
                  {user
                    ? "Your saved essays will appear here."
                    : "Sign in to save essays."}
                </div>
              )}

              {artifacts.map((artifact, index) => (
                <button
                  key={artifact.id ?? index}
                  onClick={() => openArtifact(artifact)}
                  style={{
                    ...styles.secondaryButton,
                    textAlign: "left",
                    lineHeight: 1.4,
                  }}
                >
                  {artifact.title || `Essay ${index + 1}`}
                </button>
              ))}
            </div>
          </section>

          {user && (
            <button
              onClick={() => void clearHistory()}
              disabled={clearingHistory}
              style={{
                ...styles.secondaryButton,
                width: "100%",
                color: "#ffaaaa",
                borderColor: "#743d3d",
                background: "#241515",
                opacity: clearingHistory ? 0.6 : 1,
              }}
            >
              {clearingHistory ? "Clearing history..." : "🗑 Clear my history"}
            </button>
          )}

          <div style={{ ...styles.muted, fontSize: 11, marginTop: "auto" }}>
            Lenny Growth Assistant
          </div>
        </aside>
      )}

      <section style={styles.main}>
        <header style={styles.header}>
          <div style={{ display: "flex", alignItems: "center", gap: 13 }}>
            <button
              style={styles.secondaryButton}
              onClick={() => setSidebarOpen((open) => !open)}
            >
              ☰
            </button>

            <div>
              <div style={{ fontWeight: 800, fontSize: 17 }}>
                Growth Assistant
              </div>

              <div style={{ ...styles.muted, fontSize: 12 }}>
                Ask. Explore. Build.
              </div>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 9,
              flexWrap: "wrap",
            }}
          >
            <label htmlFor="provider" style={styles.muted}>
              Provider
            </label>

            <select
              id="provider"
              value={provider}
              onChange={(event) => {
                const value = event.target.value;
                setProvider(value);
                setModel(
                  value === "ollama" ? "qwen2.5:3b" : "gemini-3.8-flash",
                );
              }}
              style={{ ...styles.input, width: 125, padding: 9 }}
            >
              <option value="ollama">Ollama</option>
              <option value="gemini">Gemini</option>
            </select>

            <label htmlFor="model" style={styles.muted}>
              Model
            </label>

            <input
              id="model"
              value={model}
              onChange={(event) => setModel(event.target.value)}
              style={{ ...styles.input, width: 145, padding: 9 }}
            />

            {user ? (
              <>
                <span
                  style={{
                    color: "#62df96",
                    fontSize: 12,
                    maxWidth: 150,
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                  }}
                  title={user.email}
                >
                  {user.email}
                </span>

                <button
                  style={styles.secondaryButton}
                  onClick={logout}
                >
                  Log out
                </button>
              </>
            ) : (
              <button
                style={styles.primaryButton}
                onClick={() => {
                  setAuthMode("login");
                  setAuthOpen(true);
                }}
              >
                Sign in
              </button>
            )}
          </div>
        </header>

        {!user && (
          <div
            style={{
              padding: "9px 22px",
              background: "#102219",
              borderBottom: "1px solid #28513a",
              color: "#b7d5c2",
              fontSize: 12,
              textAlign: "center",
            }}
          >
            Guest mode: chat and generate essays freely.{" "}
            <button
              onClick={() => {
                setAuthMode("register");
                setAuthOpen(true);
              }}
              style={{
                border: 0,
                background: "transparent",
                color: "#62df96",
                cursor: "pointer",
                fontWeight: 800,
              }}
            >
              Create an account
            </button>{" "}
            to save your work.
          </div>
        )}

        <nav
          style={{
            display: "flex",
            gap: 9,
            padding: "13px 24px",
            borderBottom: "1px solid #183b29",
          }}
        >
          <button
            onClick={() => setActiveTab("chat")}
            style={{
              ...styles.secondaryButton,
              background: activeTab === "chat" ? "#17452c" : "#0d1d14",
            }}
          >
            Chat
          </button>

          <button
            onClick={() => setActiveTab("essay")}
            style={{
              ...styles.secondaryButton,
              background: activeTab === "essay" ? "#17452c" : "#0d1d14",
            }}
          >
            Ship 30 for 30
          </button>
        </nav>

        {error && (
          <div
            role="alert"
            style={{
              margin: "14px 22px 0",
              padding: 12,
              border: "1px solid #9b4848",
              background: "#2b1717",
              borderRadius: 10,
              color: "#ffcaca",
            }}
          >
            {error}

            <button
              onClick={() => setError("")}
              style={{
                ...styles.secondaryButton,
                float: "right",
                padding: "3px 8px",
              }}
            >
              Dismiss
            </button>
          </div>
        )}

        {activeTab === "chat" ? (
          <>
            <div style={styles.content}>
              {messages.map((message, index) => (
                <article
                  key={`${sessionId}-${index}-${message.role}`}
                  style={{
                    ...styles.card,
                    borderColor:
                      message.role === "user" ? "#315a43" : "#1c4931",
                    marginLeft: message.role === "user" ? "12%" : 0,
                  }}
                >
                  <div
                    style={{
                      ...styles.label,
                      color:
                        message.role === "user" ? "#b8a6ff" : "#62df96",
                      marginBottom: 10,
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
                        borderTop: "1px solid #28513a",
                        paddingTop: 10,
                        fontSize: 12,
                        color: "#9db9a7",
                      }}
                    >
                      <strong>Sources</strong>

                      <ul>
                        {message.sources.map((source, sourceIndex) => (
                          <li key={sourceIndex}>
                            {typeof source === "string"
                              ? source
                              : source.source || source.episode || "Transcript"}
                          </li>
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
                        style={styles.secondaryButton}
                        onClick={() => void copyText(message.content)}
                      >
                        Copy
                      </button>

                      <button
                        style={styles.secondaryButton}
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
                <div style={{ color: "#9db9a7", padding: 12 }}>
                  Lenny is thinking...
                </div>
              )}
            </div>

            <form
              onSubmit={(event) => void sendMessage(event)}
              style={{
                position: "sticky",
                bottom: 0,
                borderTop: "1px solid #183b29",
                background: "#08160f",
                padding: 16,
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: 10,
                  maxWidth: 980,
                  margin: "0 auto",
                  alignItems: "flex-end",
                }}
              >
                <textarea
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  onKeyDown={handleComposerKeyDown}
                  placeholder="Ask about activation, retention, growth loops..."
                  rows={2}
                  style={{
                    ...styles.input,
                    flex: 1,
                    resize: "vertical",
                    minHeight: 50,
                    maxHeight: 180,
                    lineHeight: 1.5,
                  }}
                />

                <button
                  type="submit"
                  disabled={loading || !input.trim()}
                  style={{
                    ...styles.primaryButton,
                    opacity: loading || !input.trim() ? 0.55 : 1,
                  }}
                >
                  {loading ? "Thinking..." : "Send"}
                </button>
              </div>

              <div
                style={{
                  maxWidth: 980,
                  margin: "8px auto 0",
                  ...styles.muted,
                  fontSize: 11,
                }}
              >
                Enter to send · Shift + Enter for a new line
              </div>
            </form>
          </>
        ) : (
          <div style={{ ...styles.content, maxWidth: 820 }}>
            <div style={styles.card}>
              <div
                style={{
                  color: "#62df96",
                  fontWeight: 800,
                  fontSize: 11,
                  letterSpacing: 1.2,
                }}
              >
                LENNY WRITING STUDIO
              </div>

              <h1 style={{ fontSize: 27, margin: "10px 0" }}>
                Ship 30 for 30
              </h1>

              <p
                style={{
                  ...styles.muted,
                  fontSize: 14,
                  lineHeight: 1.65,
                }}
              >
                Turn a focused product-growth idea into a structured,
                practical essay.
              </p>

              <label
                htmlFor="essay-topic"
                style={{
                  ...styles.label,
                  display: "block",
                  margin: "22px 0 9px",
                }}
              >
                Essay topic
              </label>

              <textarea
                id="essay-topic"
                value={essayTopic}
                onChange={(event) => setEssayTopic(event.target.value)}
                placeholder="Example: How early-stage SaaS products can improve user activation..."
                rows={5}
                style={{
                  ...styles.input,
                  resize: "vertical",
                  lineHeight: 1.6,
                }}
              />

              <button
                disabled={essayLoading || !essayTopic.trim()}
                onClick={() => void generateEssay()}
                style={{
                  ...styles.primaryButton,
                  marginTop: 13,
                  opacity: essayLoading || !essayTopic.trim() ? 0.55 : 1,
                }}
              >
                {essayLoading ? "Writing your essay..." : "Generate essay"}
              </button>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
