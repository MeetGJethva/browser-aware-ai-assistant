window.__Highlighter__ = (function () {
  const HIGHLIGHT_CLASS = "__ai_highlight__";
  const ACTIVE_CLASS = "__ai_highlight_active__";

  // ── Inject highlight styles once ──────────────────────────────
  function injectStyles() {
    if (document.getElementById("__highlighter_styles__")) return;
    const style = document.createElement("style");
    style.id = "__highlighter_styles__";
    style.textContent = `
        .__ai_highlight__ {
          background: rgba(203, 166, 247, 0.35) !important;
          border-radius: 3px;
          cursor: pointer;
          transition: background 0.2s;
        }
        .__ai_highlight__:hover,
        .__ai_highlight_active__ {
          background: rgba(203, 166, 247, 0.7) !important;
          outline: 2px solid rgba(203, 166, 247, 0.9);
          outline-offset: 1px;
        }
        .__ai_highlight_pulse__ {
          animation: __ai_pulse__ 0.6s ease;
        }
        @keyframes __ai_pulse__ {
          0%   { background: rgba(203,166,247,0.9) !important; }
          100% { background: rgba(203,166,247,0.35) !important; }
        }
      `;
    document.head.appendChild(style);
  }

  // ── Clear all existing highlights ────────────────────────────
  function clearHighlights() {
    document.querySelectorAll(`.${HIGHLIGHT_CLASS}`).forEach((el) => {
      const parent = el.parentNode;
      parent.replaceChild(document.createTextNode(el.textContent), el);
      parent.normalize();
    });
  }

  // ── Find & highlight text using TreeWalker ────────────────────
  function highlightText(rawText) {
    injectStyles();
    clearHighlights();

    // Clean and split chunk into sentences/phrases for better matching
    const phrases = extractPhrases(rawText);
    let highlighted = 0;
    let firstEl = null;

    for (const phrase of phrases) {
      if (phrase.length < 20) continue; // skip very short phrases
      const found = findAndWrap(phrase);
      if (found) {
        highlighted++;
        if (!firstEl) firstEl = found;
      }
      if (highlighted >= 5) break; // max 5 highlights per chunk
    }

    // Scroll to first highlight
    if (firstEl) {
      firstEl.classList.add(ACTIVE_CLASS, "__ai_highlight_pulse__");
      firstEl.scrollIntoView({ behavior: "smooth", block: "center" });
      setTimeout(() => firstEl.classList.remove("__ai_highlight_pulse__"), 700);
      return true;
    }

    return false;
  }

  // ── Split chunk into matchable phrases ───────────────────────
  function extractPhrases(text) {
    // Try full text first, then sentences, then sub-phrases
    const cleaned = text.replace(/\s+/g, " ").trim();
    const sentences = cleaned
      .split(/[.!?]+/)
      .map((s) => s.trim())
      .filter((s) => s.length > 20);
    // Also try 60-char sliding windows for partial matches
    const windows = [];
    for (let i = 0; i < cleaned.length - 60; i += 40) {
      windows.push(cleaned.slice(i, i + 80));
    }
    return [cleaned, ...sentences, ...windows];
  }

  // ── Walk DOM text nodes and wrap matching text ────────────────
  function findAndWrap(phrase) {
    const normalizedPhrase = normalizeStr(phrase);
    if (normalizedPhrase.length < 15) return null;

    const walker = document.createTreeWalker(
      document.body,
      NodeFilter.SHOW_TEXT,
      {
        acceptNode(node) {
          // Skip script/style/our own extension UI
          const parent = node.parentElement;
          if (!parent) return NodeFilter.FILTER_REJECT;
          const tag = parent.tagName?.toLowerCase();
          if (
            ["script", "style", "noscript", "textarea", "input"].includes(tag)
          ) {
            return NodeFilter.FILTER_REJECT;
          }
          if (
            parent.closest("#__web_chat_ai_root__") ||
            parent.closest("#__price_panel__") ||
            parent.closest("#__web_chat_ai_bubble__")
          ) {
            return NodeFilter.FILTER_REJECT;
          }
          if (node.textContent.trim().length < 5) return NodeFilter.FILTER_SKIP;
          return NodeFilter.FILTER_ACCEPT;
        },
      }
    );

    let node;
    while ((node = walker.nextNode())) {
      const nodeText = normalizeStr(node.textContent);
      // Try to find phrase inside this text node
      const idx = nodeText.indexOf(normalizedPhrase.slice(0, 40));
      if (idx === -1) continue;

      // Found a match — wrap it
      try {
        const range = document.createRange();
        const start = node.textContent
          .toLowerCase()
          .indexOf(phrase.slice(0, 30).toLowerCase().trim());
        if (start === -1) continue;

        const end = Math.min(start + phrase.length, node.textContent.length);
        range.setStart(node, start);
        range.setEnd(node, end);

        const mark = document.createElement("mark");
        mark.className = HIGHLIGHT_CLASS;
        range.surroundContents(mark);
        return mark;
      } catch (e) {
        continue; // range may cross element boundaries, skip
      }
    }
    return null;
  }

  function normalizeStr(str) {
    return str.replace(/\s+/g, " ").trim().toLowerCase();
  }

  // ── Public API ────────────────────────────────────────────────
  return {
    highlight(sourceText) {
      return highlightText(sourceText);
    },
    clear() {
      clearHighlights();
    },
  };
})();
