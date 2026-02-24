import { useState, useEffect, useRef } from "react";
import axios from "axios";

const PROXY_BASE = "http://localhost:8090";

export default function App() {
  const [urlInput, setUrlInput] = useState("");
  const [iframeSrc, setIframeSrc] = useState("");
  const [currentUrl, setCurrentUrl] = useState("");
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [pageLoading, setPageLoading] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const messagesEndRef = useRef(null);

  const buildProxyUrl = (raw) => {
    if (!raw) return "";
    if (!raw.startsWith("http://") && !raw.startsWith("https://"))
      raw = "https://" + raw;
    return `${PROXY_BASE}/proxy?url=${encodeURIComponent(raw)}`;
  };

  const navigate = async (rawUrl) => {
    if (!rawUrl) return;
    setPageLoading(true);
    setCurrentUrl(rawUrl);
    setUrlInput(rawUrl);

    try {
      // Also update the LLM context
      await axios.post(`${PROXY_BASE}/load-url`, { url: rawUrl });
    } catch (_) {}

    setIframeSrc(buildProxyUrl(rawUrl));
    setPageLoading(false);
  };

  const handleGo = () => navigate(urlInput);

  const sendMessage = async () => {
    if (!input.trim() || chatLoading) return;
    const userMsg = input.trim();
    setInput("");
    setChatLoading(true);
    setMessages((prev) => [...prev, { role: "user", content: userMsg }]);

    try {
      const res = await axios.post(`${PROXY_BASE}/chat`, { message: userMsg });
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: res.data.answer },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "❌ Error getting response." },
      ]);
    }
    setChatLoading(false);
  };

  // Listen for navigation from inside iframe
  useEffect(() => {
    const handler = (e) => {
      if (e.data?.type === "NAVIGATE" && e.data.url) {
        navigate(e.data.url);
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div style={{ display: "flex", height: "100vh", fontFamily: "system-ui, sans-serif", background: "#f0f2f5" }}>
      
      {/* ── Left Panel ── */}
      <div style={{
        flex: 2, minWidth: "260px",
        display: "flex", flexDirection: "column",
        background: "#1e1e2e", color: "#cdd6f4",
        boxShadow: "2px 0 12px rgba(0,0,0,0.3)"
      }}>
        
        {/* Header */}
        <div style={{ padding: "16px", borderBottom: "1px solid #313244" }}>
          <h2 style={{ margin: 0, fontSize: 16, color: "#cba6f7" }}>🌐 Web Browser + AI</h2>
        </div>

        {/* URL Bar */}
        <div style={{ padding: "12px", borderBottom: "1px solid #313244" }}>
          <div style={{ display: "flex", gap: 6 }}>
            <input
              type="text"
              placeholder="Enter URL..."
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleGo()}
              style={{
                flex: 1, padding: "8px 10px", borderRadius: 6,
                border: "1px solid #45475a", background: "#313244",
                color: "#cdd6f4", fontSize: 13, outline: "none"
              }}
            />
            <button
              onClick={handleGo}
              disabled={pageLoading}
              style={{
                padding: "8px 14px", borderRadius: 6, border: "none",
                background: pageLoading ? "#45475a" : "#cba6f7",
                color: "#1e1e2e", fontWeight: "bold",
                cursor: pageLoading ? "not-allowed" : "pointer", fontSize: 13
              }}
            >
              {pageLoading ? "⏳" : "Go"}
            </button>
          </div>
          {currentUrl && (
            <div style={{ marginTop: 6, fontSize: 11, color: "#6c7086", wordBreak: "break-all" }}>
              {currentUrl}
            </div>
          )}
        </div>

        {/* Chat Messages */}
        <div style={{
          flex: 1, overflowY: "auto", padding: "12px",
          display: "flex", flexDirection: "column", gap: 10
        }}>
          {messages.length === 0 ? (
            <div style={{ color: "#6c7086", fontSize: 13, textAlign: "center", marginTop: 20 }}>
              Load a website, then ask me anything about it!
            </div>
          ) : (
            messages.map((msg, i) => (
              <div key={i} style={{
                alignSelf: msg.role === "user" ? "flex-end" : "flex-start",
                background: msg.role === "user" ? "#cba6f7" : "#313244",
                color: msg.role === "user" ? "#1e1e2e" : "#cdd6f4",
                padding: "8px 12px", borderRadius: 10,
                maxWidth: "90%", fontSize: 13, lineHeight: 1.5,
                boxShadow: "0 2px 6px rgba(0,0,0,0.2)"
              }}>
                {msg.content}
              </div>
            ))
          )}
          {chatLoading && (
            <div style={{
              alignSelf: "flex-start", background: "#313244",
              color: "#6c7086", padding: "8px 12px",
              borderRadius: 10, fontSize: 13
            }}>
              Thinking...
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Chat Input */}
        <div style={{ padding: "12px", borderTop: "1px solid #313244", display: "flex", gap: 6 }}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage()}
            placeholder="Ask about the page..."
            style={{
              flex: 1, padding: "8px 10px", borderRadius: 6,
              border: "1px solid #45475a", background: "#313244",
              color: "#cdd6f4", fontSize: 13, outline: "none"
            }}
          />
          <button
            onClick={sendMessage}
            disabled={chatLoading}
            style={{
              padding: "8px 14px", borderRadius: 6, border: "none",
              background: chatLoading ? "#45475a" : "#a6e3a1",
              color: "#1e1e2e", fontWeight: "bold",
              cursor: chatLoading ? "not-allowed" : "pointer", fontSize: 13
            }}
          >
            ➤
          </button>
        </div>
      </div>

      {/* ── Right Panel: Browser ── */}
      <div style={{ flex: 8, display: "flex", flexDirection: "column", position: "relative" }}>
        {pageLoading && (
          <div style={{
            position: "absolute", top: 0, left: 0, right: 0,
            height: 3, background: "linear-gradient(90deg, #cba6f7, #a6e3a1)",
            zIndex: 10, animation: "pulse 1s infinite"
          }} />
        )}
        {iframeSrc ? (
          <iframe
            key={iframeSrc}
            src={iframeSrc}
            style={{ flex: 8, border: "none", width: "100%" }}
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals"
            title="browser"
          />
        ) : (
          <div style={{
            flex: 8, display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            color: "#6c7086", gap: 12
          }}>
            <div style={{ fontSize: 64 }}>🌐</div>
            <div style={{ fontSize: 20, fontWeight: "bold", color: "#cdd6f4" }}>
              Enter a URL to start browsing
            </div>
            <div style={{ fontSize: 14 }}>
              Try: amazon.in, flipkart.com, wikipedia.org
            </div>
          </div>
        )}
      </div>
    </div>
  );
}