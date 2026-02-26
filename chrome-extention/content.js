(function () {
  // ── Toggle: remove if already open ──────────────────────────────
  if (document.getElementById("__web_chat_ai_root__")) {
    document.getElementById("__web_chat_ai_root__").remove();
    document.getElementById("__web_chat_ai_styles__")?.remove();
    document.getElementById("__web_chat_ai_marked__")?.remove();
    document.getElementById("__web_chat_ai_bubble__")?.remove();
    return;
  }

  const LLM_API = "http://localhost:8090/chat";

  // ── Load marked.js for Markdown rendering ───────────────────────
  function loadMarked(cb) {
    if (window.__marked_loaded__) {
      cb();
      return;
    }
    const s = document.createElement("script");
    s.id = "__web_chat_ai_marked__";
    s.src = chrome.runtime.getURL("marked.min.js");
    s.onload = () => {
      window.__marked_loaded__ = true;
      cb();
    };
    document.head.appendChild(s);
  }

  // ── Inject CSS ───────────────────────────────────────────────────
  const link = document.createElement("link");
  link.id = "__web_chat_ai_styles__";
  link.rel = "stylesheet";
  link.href = chrome.runtime.getURL("chat.css");
  document.head.appendChild(link);

  // ── Load price tracker module ────────────────────────────────────
  const priceScript = document.createElement("script");
  priceScript.src = chrome.runtime.getURL("price_tracker.js");
  document.head.appendChild(priceScript);

  const highlightScript = document.createElement("script");
  highlightScript.src = chrome.runtime.getURL("highlighter.js");
  document.head.appendChild(highlightScript);

  // ── Restore saved theme & size from storage ──────────────────────
  const savedTheme = localStorage.getItem("__chat_ai_theme__") || "dark";
  const savedW = localStorage.getItem("__chat_ai_width__");
  const savedH = localStorage.getItem("__chat_ai_height__");

  // ── Create root ──────────────────────────────────────────────────
  const root = document.createElement("div");
  root.id = "__web_chat_ai_root__";
  if (savedTheme === "light") root.classList.add("light");
  if (savedW) root.style.width = savedW;
  if (savedH) root.style.height = savedH;
  document.body.appendChild(root);

  // ── Load HTML then init ──────────────────────────────────────────
  fetch(chrome.runtime.getURL("chat.html"))
    .then((r) => r.text())
    .then((html) => {
      root.innerHTML = html;
      loadMarked(initChat);
    });

  // ────────────────────────────────────────────────────────────────
  function initChat() {
    // DOM refs
    const messagesEl = root.querySelector("#__chat_messages__");
    const inputEl = root.querySelector("#__chat_input__");
    const sendBtn = root.querySelector("#__chat_send_btn__");
    const closeBtn = root.querySelector("#__chat_close_btn__");
    const clearBtn = root.querySelector("#__chat_clear_btn__");
    const refreshBtn = root.querySelector("#__chat_refresh_btn__");
    const minimizeBtn = root.querySelector("#__chat_minimize_btn__");
    const themeBtn = root.querySelector("#__chat_theme_btn__");
    const pageLabel = root.querySelector("#__chat_page_label__");
    const suggestions = root.querySelectorAll(".__suggestion_chip__");
    const suggestionsEl = root.querySelector("#__chat_suggestions__");
    const dragHandle = root.querySelector("#__chat_drag_handle__");
    const resizeHandle = root.querySelector("#__chat_resize_handle__");

    // State
    let pageContext = "";
    let isLoading = false;
    let unreadCount = 0;
    let isDark = savedTheme !== "light";

    pageLabel.textContent = window.location.hostname;

    // ── Extract page text ────────────────────────────────────────
    function extractPageContent() {
      const clone = document.body.cloneNode(true);
      clone
        .querySelectorAll(
          "script,style,noscript,nav,footer,header,aside,[aria-hidden='true']"
        )
        .forEach((el) => el.remove());
      return (clone.innerText || clone.textContent || "")
        .replace(/\s+/g, " ")
        .trim();
    }

    pageContext = extractPageContent();

    // ── Render markdown safely ───────────────────────────────────
    function renderMarkdown(text) {
      if (window.marked) {
        try {
          return window.marked.parse(text, { breaks: true, gfm: true });
        } catch (e) {}
      }
      // Fallback: escape HTML
      return text
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/\n/g, "<br>");
    }

    // ── Add message bubble ───────────────────────────────────────
    function addMessage(content, type = "ai", sources = []) {
      const empty = messagesEl.querySelector(".__chat_empty__");
      if (empty) empty.remove();

      // Wrapper holds bubble + source button
      const wrapper = document.createElement("div");
      wrapper.style.cssText = `display:flex;flex-direction:column;align-items:${
        type === "user" ? "flex-end" : "flex-start"
      };max-width:88%;${
        type === "user" ? "align-self:flex-end" : "align-self:flex-start"
      }`;

      const bubble = document.createElement("div");
      bubble.className = `__msg_bubble__ ${
        type === "user"
          ? "__msg_user__"
          : type === "error"
          ? "__msg_error__"
          : "__msg_ai__"
      }`;
      bubble.style.maxWidth = "100%";

      if (type === "ai") {
        bubble.innerHTML = renderMarkdown(content);
      } else {
        bubble.textContent = content;
      }

      wrapper.appendChild(bubble);

      // Add source highlight button for AI messages with sources
      if (type === "ai" && sources && sources.length > 0) {
        const sourceBtn = document.createElement("button");
        sourceBtn.className = "__msg_source_btn__";
        sourceBtn.innerHTML = `🔍 Show source`;

        let isActive = false;
        sourceBtn.addEventListener("click", () => {
          isActive = !isActive;

          // Clear all other active buttons
          root.querySelectorAll(".__msg_source_btn__.active").forEach((b) => {
            b.classList.remove("active");
            b.innerHTML = "🔍 Show source";
          });

          if (isActive) {
            // Highlight the most relevant source (first chunk)
            const found = window.__Highlighter__?.highlight(sources[0]);
            if (found) {
              sourceBtn.classList.add("active");
              sourceBtn.innerHTML = `✕ Clear highlight`;
            } else {
              sourceBtn.innerHTML = `⚠️ Not found`;
              setTimeout(() => {
                sourceBtn.innerHTML = "🔍 Show source";
              }, 2000);
              isActive = false;
            }
          } else {
            window.__Highlighter__?.clear();
            sourceBtn.innerHTML = "🔍 Show source";
          }
        });

        wrapper.appendChild(sourceBtn);
      }

      messagesEl.appendChild(wrapper);
      messagesEl.scrollTop = messagesEl.scrollHeight;

      if (
        !root.isConnected ||
        document.getElementById("__web_chat_ai_bubble__")
      ) {
        if (type === "ai") {
          unreadCount++;
          updateBubbleBadge();
        }
      }
    }

    // ── Typing indicator ─────────────────────────────────────────
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

    // ── Send message ─────────────────────────────────────────────
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
        addMessage(
          data.answer || "No response received.",
          "ai",
          data.sources || []
        );
      } catch (err) {
        removeTyping();
        addMessage(`⚠️ Could not connect to AI.\n${err.message}`, "error");
      }

      isLoading = false;
      sendBtn.disabled = false;
    }

    // ── Button Events ────────────────────────────────────────────
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
      document.getElementById("__web_chat_ai_bubble__")?.remove();
    });

    clearBtn.addEventListener("click", () => {
      messagesEl.innerHTML = `
        <div class="__chat_empty__">
          <div>🧠</div>
          <div>Chat cleared.<br/>Ask me anything about this page!</div>
        </div>
      `;
      suggestionsEl.style.display = "flex";
      unreadCount = 0;
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

    // ── Feature 1: Minimize to Bubble ────────────────────────────
    function updateBubbleBadge() {
      const bubble = document.getElementById("__web_chat_ai_bubble__");
      if (!bubble) return;
      let badge = bubble.querySelector(".__bubble_badge__");
      if (unreadCount > 0) {
        if (!badge) {
          badge = document.createElement("div");
          badge.className = "__bubble_badge__";
          bubble.appendChild(badge);
        }
        badge.textContent = unreadCount;
      } else {
        badge?.remove();
      }
    }

    function minimize() {
      // Save current position
      const rect = root.getBoundingClientRect();
      const bubbleBottom =
        window.innerHeight - rect.bottom + rect.height / 2 - 28;
      const bubbleRight = window.innerWidth - rect.right + rect.width / 2 - 28;

      root.style.display = "none";

      // Create bubble
      const bubble = document.createElement("div");
      bubble.id = "__web_chat_ai_bubble__";
      bubble.innerHTML = "🤖";
      bubble.style.bottom = Math.max(16, bubbleBottom) + "px";
      bubble.style.right = Math.max(16, bubbleRight) + "px";
      document.body.appendChild(bubble);

      updateBubbleBadge();

      // Drag bubble
      let bDrag = false,
        bStartX,
        bStartY,
        bLeft,
        bBottom;
      bubble.addEventListener("mousedown", (e) => {
        bDrag = true;
        bStartX = e.clientX;
        bStartY = e.clientY;
        const r = bubble.getBoundingClientRect();
        bLeft = r.left;
        bBottom = window.innerHeight - r.bottom;
        e.preventDefault();
      });

      document.addEventListener("mousemove", (e) => {
        if (!bDrag) return;
        const dx = e.clientX - bStartX;
        const dy = e.clientY - bStartY;
        bubble.style.left =
          Math.max(8, Math.min(window.innerWidth - 64, bLeft + dx)) + "px";
        bubble.style.bottom =
          Math.max(8, Math.min(window.innerHeight - 64, bBottom - dy)) + "px";
        bubble.style.right = "auto";
      });

      document.addEventListener("mouseup", () => {
        bDrag = false;
      });

      // Click to restore
      bubble.addEventListener("click", (e) => {
        if (
          Math.abs(e.clientX - bStartX) > 5 ||
          Math.abs(e.clientY - bStartY) > 5
        )
          return;
        restore(bubble);
      });
    }

    function restore(bubble) {
      bubble.remove();
      root.style.display = "flex";
      unreadCount = 0;
      updateBubbleBadge();
    }

    minimizeBtn.addEventListener("click", minimize);

    // ── Feature 2: Dark / Light Mode Toggle ─────────────────────
    themeBtn.addEventListener("click", () => {
      isDark = !isDark;
      root.classList.toggle("light", !isDark);
      localStorage.setItem("__chat_ai_theme__", isDark ? "dark" : "light");
    });

    // ── Price Tracker Button ─────────────────────────────────────
    const priceBtn = root.querySelector("#__chat_price_btn__");
    priceBtn?.addEventListener("click", () => {
      const isLight = root.classList.contains("light");
      // Wait for script to load if needed
      if (window.__PriceTracker__) {
        window.__PriceTracker__.trackAndShow(isLight);
      } else {
        setTimeout(() => window.__PriceTracker__?.trackAndShow(isLight), 500);
      }
    });

    // ── Feature 3: Resize Handle ─────────────────────────────────
    let isResizing = false;
    let resizeStartX, resizeStartY, resizeStartW, resizeStartH;

    resizeHandle.addEventListener("mousedown", (e) => {
      isResizing = true;
      resizeStartX = e.clientX;
      resizeStartY = e.clientY;
      resizeStartW = root.offsetWidth;
      resizeStartH = root.offsetHeight;
      e.preventDefault();
      e.stopPropagation();
    });

    document.addEventListener("mousemove", (e) => {
      if (!isResizing) return;
      const dx = resizeStartX - e.clientX; // dragging left = wider
      const dy = resizeStartY - e.clientY; // dragging up   = taller
      const newW = Math.max(
        280,
        Math.min(window.innerWidth - 32, resizeStartW + dx)
      );
      const newH = Math.max(
        300,
        Math.min(window.innerHeight - 32, resizeStartH + dy)
      );
      root.style.width = newW + "px";
      root.style.height = newH + "px";
      root.style.maxWidth = "none";
      root.style.maxHeight = "none";
    });

    document.addEventListener("mouseup", () => {
      if (isResizing) {
        isResizing = false;
        // Save to localStorage
        localStorage.setItem("__chat_ai_width__", root.style.width);
        localStorage.setItem("__chat_ai_height__", root.style.height);
      }
    });

    // ── Drag to Move ─────────────────────────────────────────────
    let isDragging = false;
    let startX, startY, startLeft, startBottom;

    dragHandle.addEventListener("mousedown", (e) => {
      if (e.target.closest("button")) return;
      if (document.getElementById("__price_panel__")) return; // price panel open
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
  }
})();
