(function () {
  // ── Toggle: remove if already open ──────────────────────────────
  if (document.getElementById("__web_chat_ai_root__")) {
    document.getElementById("__web_chat_ai_root__").remove();
    document.getElementById("__web_chat_ai_styles__")?.remove();
    return;
  }

  const EXT_BASE = chrome.runtime.getURL("");
  const LLM_API = "http://localhost:8090/chat";

  // ── Inject CSS ───────────────────────────────────────────────────
  const link = document.createElement("link");
  link.id = "__web_chat_ai_styles__";
  link.rel = "stylesheet";
  link.href = chrome.runtime.getURL("chat.css");
  document.head.appendChild(link);

  // ── Create root container ────────────────────────────────────────
  const root = document.createElement("div");
  root.id = "__web_chat_ai_root__";
  document.body.appendChild(root);

  // ── Load HTML template ───────────────────────────────────────────
  fetch(chrome.runtime.getURL("chat.html"))
    .then((r) => r.text())
    .then((html) => {
      root.innerHTML = html;
      initChat();
    });

  // ── Init all logic after HTML is injected ────────────────────────
  function initChat() {
    // DOM refs
    const messagesEl = root.querySelector("#__chat_messages__");
    const inputEl = root.querySelector("#__chat_input__");
    const sendBtn = root.querySelector("#__chat_send_btn__");
    const closeBtn = root.querySelector("#__chat_close_btn__");
    const clearBtn = root.querySelector("#__chat_clear_btn__");
    const refreshBtn = root.querySelector("#__chat_refresh_btn__");
    const pageLabel = root.querySelector("#__chat_page_label__");
    const suggestions = root.querySelectorAll(".__suggestion_chip__");
    const suggestionsEl = root.querySelector("#__chat_suggestions__");
    const dragHandle = root.querySelector("#__chat_drag_handle__");

    // State
    let pageContext = "";
    let isLoading = false;

    // Set page label
    pageLabel.textContent = window.location.hostname;

    // ── Extract page text ──────────────────────────────────────────
    function extractPageContent() {
      const clone = document.body.cloneNode(true);
      clone
        .querySelectorAll(
          "script, style, noscript, nav, footer, header, aside, [aria-hidden='true']"
        )
        .forEach((el) => el.remove());
      return (clone.innerText || clone.textContent || "")
        .replace(/\s+/g, " ")
        .trim()
        .slice(0, 8000);
    }

    pageContext = extractPageContent();

    // ── Add message bubble ─────────────────────────────────────────
    function addMessage(content, type = "ai") {
      const empty = messagesEl.querySelector(".__chat_empty__");
      if (empty) empty.remove();

      const bubble = document.createElement("div");
      bubble.className = `__msg_bubble__ ${
        type === "user"
          ? "__msg_user__"
          : type === "error"
          ? "__msg_error__"
          : "__msg_ai__"
      }`;
      bubble.textContent = content;
      messagesEl.appendChild(bubble);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    // ── Typing indicator ───────────────────────────────────────────
    function showTyping() {
      const el = document.createElement("div");
      el.className = "__chat_typing__";
      el.id = "__typing_indicator__";
      el.innerHTML = `
          <div class="__typing_dot__"></div>
          <div class="__typing_dot__"></div>
          <div class="__typing_dot__"></div>
        `;
      messagesEl.appendChild(el);
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }

    function removeTyping() {
      messagesEl.querySelector("#__typing_indicator__")?.remove();
    }

    // ── Send message ───────────────────────────────────────────────
    async function sendMessage() {
      const text = inputEl.value.trim();
      if (!text || isLoading) return;

      isLoading = true;
      sendBtn.disabled = true;
      inputEl.value = "";
      inputEl.style.height = "auto";

      addMessage(text, "user");
      showTyping();
      suggestionsEl.style.display = "none";

      try {
        const res = await fetch(LLM_API, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message: text, context: pageContext }),
        });

        if (!res.ok) throw new Error(`Server error: ${res.status}`);
        const data = await res.json();
        removeTyping();
        addMessage(data.answer || "No response received.", "ai");
      } catch (err) {
        removeTyping();
        addMessage(`⚠️ Could not connect to AI.\n${err.message}`, "error");
      }

      isLoading = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }

    // ── Button events ──────────────────────────────────────────────
    sendBtn.addEventListener("click", sendMessage);

    inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    });

    inputEl.addEventListener("input", () => {
      inputEl.style.height = "auto";
      inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + "px";
    });

    closeBtn.addEventListener("click", () => {
      root.remove();
      document.getElementById("__web_chat_ai_styles__")?.remove();
    });

    clearBtn.addEventListener("click", () => {
      messagesEl.innerHTML = `
          <div class="__chat_empty__">
            <div>🧠</div>
            <div>Chat cleared.<br/>Ask me anything about this page!</div>
          </div>
        `;
      suggestionsEl.style.display = "flex";
    });

    refreshBtn.addEventListener("click", () => {
      pageContext = extractPageContent();
      pageLabel.textContent = window.location.hostname + " ✓";
      setTimeout(
        () => (pageLabel.textContent = window.location.hostname),
        2000
      );
    });

    suggestions.forEach((chip) => {
      chip.addEventListener("click", () => {
        inputEl.value = chip.textContent;
        sendMessage();
      });
    });

    // ── Drag to move ───────────────────────────────────────────────
    let isDragging = false;
    let startX, startY, startLeft, startBottom;

    dragHandle.addEventListener("mousedown", (e) => {
      isDragging = true;
      startX = e.clientX;
      startY = e.clientY;
      const rect = root.getBoundingClientRect();
      startLeft = rect.left;
      startBottom = window.innerHeight - rect.bottom;
      root.style.transition = "none";
    });

    document.addEventListener("mousemove", (e) => {
      if (!isDragging) return;
      const dx = e.clientX - startX;
      const dy = e.clientY - startY;
      const newLeft = Math.max(
        8,
        Math.min(window.innerWidth - root.offsetWidth - 8, startLeft + dx)
      );
      const newBottom = Math.max(
        8,
        Math.min(window.innerHeight - root.offsetHeight - 8, startBottom - dy)
      );
      root.style.right = "auto";
      root.style.left = newLeft + "px";
      root.style.bottom = newBottom + "px";
    });

    document.addEventListener("mouseup", () => {
      isDragging = false;
    });

    // Focus input on open
    inputEl.focus();
  }
})();
