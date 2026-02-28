window.__YouTubeChat__ = (function () {

    let currentVideoId  = null;
    let isLoaded        = false;
    let isYouTubePage   = false;
  
    // ── Detect if we're on YouTube ──────────────────────────────────
    function detectYouTube() {
      isYouTubePage = window.location.hostname.includes("youtube.com") &&
                      window.location.pathname === "/watch";
      return isYouTubePage;
    }
  
    function getVideoId() {
      const params = new URLSearchParams(window.location.search);
      return params.get("v");
    }
  
    // ── Jump video to timestamp ─────────────────────────────────────
    function seekTo(seconds) {
      const video = document.querySelector("video");
      if (video) {
        video.currentTime = seconds;
        video.play();
      }
    }
  
    // ── Load transcript via backend ─────────────────────────────────
    async function loadTranscript(statusEl) {
      const videoId = getVideoId();
      if (!videoId) return false;
  
      currentVideoId = videoId;
      isLoaded       = false;
  
      if (statusEl) {
        statusEl.textContent = "⏳ Loading transcript...";
        statusEl.style.color = "#89b4fa";
      }
  
      try {
        const res = await fetch("http://localhost:8090/youtube/load", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url: window.location.href }),
        });
        const data = await res.json();
  
        if (data.success) {
          isLoaded = true;
          if (statusEl) {
            statusEl.textContent = `✓ ${data.message}`;
            statusEl.style.color = "#a6e3a1";
            setTimeout(() => {
              statusEl.textContent = `📺 ${data.total_duration} video loaded`;
            }, 2000);
          }
          return true;
        } else {
          if (statusEl) {
            statusEl.textContent = "⚠️ " + data.error;
            statusEl.style.color = "#f38ba8";
          }
          return false;
        }
      } catch (e) {
        if (statusEl) {
          statusEl.textContent = "⚠️ Backend not reachable";
          statusEl.style.color = "#f38ba8";
        }
        return false;
      }
    }
  
    // ── Send YouTube-specific question ──────────────────────────────
    async function askQuestion(message) {
      if (!currentVideoId || !isLoaded) {
        return {
          answer: "⚠️ Transcript not loaded yet. Click '📺 Load Video' first.",
          timelines: []
        };
      }
  
      const res = await fetch("http://localhost:8090/youtube/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_id: currentVideoId, message }),
      });
      return await res.json();
    }
  
    // ── Render timeline markers below a message bubble ──────────────
    function renderTimelines(timelines, wrapper) {
      if (!timelines || timelines.length === 0) return;
  
      const container = document.createElement("div");
      container.style.cssText = `
        display: flex;
        flex-wrap: wrap;
        gap: 6px;
        margin-top: 6px;
      `;
  
      timelines.forEach(tl => {
        const chip = document.createElement("button");
        chip.style.cssText = `
          display: inline-flex;
          align-items: center;
          gap: 5px;
          padding: 4px 10px;
          background: rgba(137,180,250,0.12);
          border: 1px solid rgba(137,180,250,0.4);
          border-radius: 20px;
          color: #89b4fa;
          font-size: 11px;
          cursor: pointer;
          font-family: inherit;
          transition: all 0.15s;
          white-space: nowrap;
        `;
        chip.innerHTML = `▶ ${tl.label}`;
        chip.title = tl.text;
  
        chip.addEventListener("mouseenter", () => {
          chip.style.background = "rgba(137,180,250,0.25)";
          chip.style.borderColor = "rgba(137,180,250,0.8)";
        });
        chip.addEventListener("mouseleave", () => {
          chip.style.background = "rgba(137,180,250,0.12)";
          chip.style.borderColor = "rgba(137,180,250,0.4)";
        });
        chip.addEventListener("click", () => seekTo(tl.start_time));
  
        container.appendChild(chip);
      });
  
      wrapper.appendChild(container);
    }
  
    return {
      detectYouTube,
      getVideoId,
      loadTranscript,
      askQuestion,
      renderTimelines,
      isLoaded: () => isLoaded,
      isYouTube: () => isYouTubePage,
    };
  
  })();