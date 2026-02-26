window.__PriceTracker__ = (function () {
  let panelEl = null; // the panel DOM node
  let isDragging = false;
  let dStartX, dStartY, dLeft, dTop;

  // ── Inject CSS once ─────────────────────────────────────────────
  function injectCSS() {
    if (document.getElementById("__price_tracker_styles__")) return;
    const link = document.createElement("link");
    link.id = "__price_tracker_styles__";
    link.rel = "stylesheet";
    link.href = chrome.runtime.getURL("price_tracker.css");
    document.head.appendChild(link);
  }

  // ── Extract product info from page ──────────────────────────────
  function extractProductInfo() {
    return {
      url: window.location.href,
      title: extractTitle(),
      price: extractPrice(),
      image: extractImage(),
    };
  }

  function extractTitle() {
    const selectors = [
      "#productTitle",
      ".B_NuCI",
      "h1.product-title",
      "h1[class*='title']",
      "h1[class*='product']",
      "h1[class*='name']",
      ".pdp-title",
      "#title",
      "h1",
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el?.textContent?.trim()) return el.textContent.trim().slice(0, 200);
    }
    return document.title.slice(0, 200);
  }

  function extractPrice() {
    const selectors = [
      ".a-price-whole",
      "#priceblock_ourprice",
      "#priceblock_dealprice",
      ".a-offscreen",
      "._30jeq3",
      "._16Jk6d",
      "[class*='price']:not([class*='was']):not([class*='old'])",
      "[id*='price']",
      "[class*='Price']",
      ".price",
      "#price",
    ];
    for (const sel of selectors) {
      for (const el of document.querySelectorAll(sel)) {
        const text = el.textContent.trim();
        if (/[\d,]+/.test(text) && /[₹$€£]|rs\.?/i.test(text)) {
          return text.replace(/\s+/g, "").slice(0, 30);
        }
      }
    }
    const match = document.body.innerText.match(/[₹$€£]\s*[\d,]+(\.\d{1,2})?/);
    return match ? match[0].replace(/\s+/g, "") : null;
  }

  function extractImage() {
    const selectors = [
      "#landingImage",
      "._396cs4",
      "img[class*='product']",
      "img[id*='product']",
      ".product-image img",
      "img[class*='main']",
    ];
    for (const sel of selectors) {
      const el = document.querySelector(sel);
      if (el?.src) return el.src;
    }
    return "";
  }

  // ── Panel size mirrors the chat window size ──────────────────────
  function getChatRoot() {
    return document.getElementById("__web_chat_ai_root__");
  }

  function getPanelRect() {
    const chat = getChatRoot();
    if (!chat) return { left: 24, top: 80, width: 360, height: 500 };
    const r = chat.getBoundingClientRect();
    return {
      left: r.left,
      top: r.top,
      width: r.width,
      height: r.height,
    };
  }

  // ── Create & position panel ──────────────────────────────────────
  function createPanel(isLight) {
    removePanel();
    injectCSS();

    fetch(chrome.runtime.getURL("price_tracker.html"))
      .then((r) => r.text())
      .then((html) => {
        panelEl = document.createElement("div");
        panelEl.id = "__price_panel__";
        if (isLight) panelEl.classList.add("light");

        // Position + size = exactly match chat window
        const rect = getPanelRect();
        panelEl.style.cssText = `
            left:   ${rect.left}px;
            top:    ${rect.top}px;
            width:  ${rect.width}px;
            height: ${rect.height}px;
          `;

        panelEl.innerHTML = html;
        document.body.appendChild(panelEl);

        // Wire close button
        panelEl
          .querySelector("#__price_close__")
          ?.addEventListener("click", removePanel);

        // Wire drag on header
        const header = panelEl.querySelector(".__price_header__");
        if (header) enableDrag(header);

        // Show loading state immediately
        setLoading();
      });
  }

  function removePanel() {
    if (panelEl) {
      panelEl.remove();
      panelEl = null;
    }
  }

  // ── Drag the panel (completely independent of chat drag) ─────────
  function enableDrag(handle) {
    handle.addEventListener("mousedown", (e) => {
      if (e.target.closest("button")) return;
      isDragging = true;
      const rect = panelEl.getBoundingClientRect();
      dStartX = e.clientX;
      dStartY = e.clientY;
      dLeft = rect.left;
      dTop = rect.top;
      e.preventDefault();
      e.stopPropagation();
    });
  }

  // Global mousemove / mouseup for panel drag
  document.addEventListener("mousemove", (e) => {
    if (!isDragging || !panelEl) return;
    const dx = e.clientX - dStartX;
    const dy = e.clientY - dStartY;
    const W = panelEl.offsetWidth;
    const H = panelEl.offsetHeight;
    const newLeft = Math.max(
      8,
      Math.min(window.innerWidth - W - 8, dLeft + dx)
    );
    const newTop = Math.max(8, Math.min(window.innerHeight - H - 8, dTop + dy));
    panelEl.style.left = newLeft + "px";
    panelEl.style.top = newTop + "px";
  });

  document.addEventListener("mouseup", () => {
    isDragging = false;
  });

  // ── Panel content states ─────────────────────────────────────────
  function setLoading() {
    const body = panelEl?.querySelector("#__price_body__");
    if (!body) return;
    body.innerHTML = `
        <div class="__price_loading__">
          <span>📊</span>
          <span>Tracking price...</span>
        </div>
      `;
  }

  function setError(msg) {
    const body = panelEl?.querySelector("#__price_body__");
    if (!body) return;
    body.innerHTML = `<div class="__price_error__">${msg}</div>`;
  }

  function setData(data) {
    const body = panelEl?.querySelector("#__price_body__");
    if (!body) return;

    const c = data.currency;
    const trendIcon =
      data.trend === "up" ? "📈" : data.trend === "down" ? "📉" : "➡️";
    const chartSvg = buildSparkline(data.history);

    body.innerHTML = `
        <!-- Product -->
        <div class="__price_product_row__">
          ${
            data.image_url
              ? `<img src="${data.image_url}" class="__price_product_img__"
                 onerror="this.style.display='none'">`
              : ""
          }
          <div class="__price_product_title__">${data.title || "Product"}</div>
        </div>
  
        <!-- Current price -->
        <div class="__price_current_card__">
          <div>
            <div class="__price_current_label__">Current Price</div>
            <div class="__price_current_value__">${c}${data.current.toLocaleString()}</div>
          </div>
          <div class="__price_trend_icon__">${trendIcon}</div>
        </div>
  
        <!-- Stats -->
        <div class="__price_stats_grid__">
          <div class="__price_stat_card__">
            <div class="__price_stat_label__">Lowest</div>
            <div class="__price_stat_value__ lowest">${c}${data.lowest.toLocaleString()}</div>
          </div>
          <div class="__price_stat_card__">
            <div class="__price_stat_label__">Highest</div>
            <div class="__price_stat_value__ highest">${c}${data.highest.toLocaleString()}</div>
          </div>
          <div class="__price_stat_card__">
            <div class="__price_stat_label__">Average</div>
            <div class="__price_stat_value__ average">${c}${data.average.toLocaleString()}</div>
          </div>
        </div>
  
        <!-- Chart -->
        <div class="__price_chart_box__">
          <div class="__price_chart_label__">Price History (${
            data.data_points
          } records)</div>
          ${chartSvg}
          ${
            data.data_points < 3
              ? `<div class="__price_chart_hint__">Visit again to build more history</div>`
              : ""
          }
        </div>
      `;
  }

  // ── SVG Sparkline ────────────────────────────────────────────────
  function buildSparkline(history) {
    if (!history || history.length < 2) {
      return `<div style="text-align:center;color:#6c7086;font-size:12px;padding:16px 0;">Not enough data yet</div>`;
    }

    const W = 300,
      H = 80,
      pad = 8;
    const prices = history.map((h) => h.price);
    const dates = history.map((h) =>
      new Date(h.date).toLocaleDateString("en-IN", {
        month: "short",
        day: "numeric",
      })
    );

    const minP = Math.min(...prices);
    const maxP = Math.max(...prices);
    const range = maxP - minP || 1;

    const pts = prices.map((p, i) => {
      const x = pad + (i / (prices.length - 1)) * (W - pad * 2);
      const y = H - pad - ((p - minP) / range) * (H - pad * 2);
      return [x, y];
    });

    const polyline = pts.map((p) => p.join(",")).join(" ");
    const areaClose = `${pts[pts.length - 1][0]},${H} ${pts[0][0]},${H}`;

    const labelIdx = [0, Math.floor(prices.length / 2), prices.length - 1];
    const labels = labelIdx
      .map(
        (i) =>
          `<text x="${pts[i][0]}" y="${
            H + 14
          }" font-size="9" fill="#6c7086" text-anchor="middle">${
            dates[i]
          }</text>`
      )
      .join("");

    const [lx, ly] = pts[pts.length - 1];

    return `
        <svg width="100%" viewBox="0 0 ${W} ${
      H + 20
    }" xmlns="http://www.w3.org/2000/svg" style="overflow:visible;display:block;">
          <defs>
            <linearGradient id="__pgr__" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%"   stop-color="rgba(203,166,247,0.25)"/>
              <stop offset="100%" stop-color="rgba(203,166,247,0)"/>
            </linearGradient>
          </defs>
          <polygon points="${polyline} ${areaClose}" fill="url(#__pgr__)"/>
          <polyline points="${polyline}" fill="none" stroke="#cba6f7" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="${lx}" cy="${ly}" r="4"  fill="#89b4fa"/>
          <circle cx="${lx}" cy="${ly}" r="7"  fill="#89b4fa" opacity="0.25"/>
          ${labels}
        </svg>
      `;
  }

  // ── Public API ───────────────────────────────────────────────────
  async function trackAndShow(isLight) {
    const info = extractProductInfo();
    createPanel(isLight); // opens immediately with loader

    if (!info.price) {
      // Wait for DOM to be ready then show error
      setTimeout(
        () =>
          setError(
            "❌ Could not detect a price on this page.\nTry visiting a specific product page."
          ),
        100
      );
      return;
    }

    try {
      const res = await fetch("http://localhost:8090/track-price", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: info.url,
          title: info.title,
          price: info.price,
          image_url: info.image,
        }),
      });
      const data = await res.json();
      if (!data.success) {
        setError("⚠️ " + (data.error || "Could not track price."));
      } else {
        setData(data);
      }
    } catch (e) {
      setError("⚠️ Backend not reachable.\n" + e.message);
    }
  }

  return { trackAndShow, removePanel };
})();
