# 🤖 Browser Aware AI Assistant

> Chat with any webpage using AI. Ask questions, track prices, highlight sources, and explore YouTube videos — all from a floating chat window directly in your browser.

[![GitHub](https://img.shields.io/badge/GitHub-MeetGJethva%2Fbrowser--aware--ai--assistant-181717?style=flat&logo=github)](https://github.com/MeetGJethva/browser-aware-ai-assistant)
![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat&logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100%2B-009688?style=flat&logo=fastapi)
![Chrome Extension](https://img.shields.io/badge/Chrome-Extension%20MV3-4285F4?style=flat&logo=googlechrome)

---

## ✨ Features

| Feature                      | Description                                                                       |
| ---------------------------- | --------------------------------------------------------------------------------- |
| 💬 **Chat with any webpage** | Ask questions about any website you are browsing                                  |
| 🧠 **RAG Pipeline**          | Smart chunking + semantic search — only relevant content sent to LLM              |
| 🔍 **Source Highlighting**   | AI highlights the exact text on the page it used to answer                        |
| 📈 **Price Tracker**         | Track price history with charts on any product page                               |
| 📺 **YouTube Q&A**           | Ask questions about any YouTube video using its transcript + clickable timestamps |
| 🌙 **Dark / Light Mode**     | Toggle between themes, saved across sessions                                      |
| 📌 **Minimize to Bubble**    | Collapse chat to a floating icon with unread badge                                |
| ↔️ **Resizable & Draggable** | Resize and drag the chat window anywhere on screen                                |
| 📝 **Markdown Rendering**    | AI responses rendered with full markdown — code, lists, bold, tables              |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Chrome Extension                       │
│                                                         │
│  content.js        ──► Extracts clean page text         │
│  youtube_chat.js   ──► YouTube transcript Q&A           │
│  price_tracker.js  ──► Price extraction & display       │
│  highlighter.js    ──► Highlights source text on page   │
└──────────────────────────┬──────────────────────────────┘
                           │ HTTP (localhost:8090)
┌──────────────────────────▼──────────────────────────────┐
│                   FastAPI Backend                        │
│                                                         │
│  /chat          ──► RAG pipeline → LLM → answer         │
│  /track-price   ──► Store price with timestamp          │
│  /price-history ──► Return price history + stats        │
│  /youtube/load  ──► Fetch & embed YouTube transcript    │
│  /youtube/chat  ──► Answer question with timestamps     │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│                     Data Layer                           │
│                                                         │
│  SQLite (rag_cache.db) ──► Chunk embedding cache        │
│  SQLite (prices.db)    ──► Price history                │
│  SentenceTransformers  ──► Local embeddings (no API)    │
└─────────────────────────────────────────────────────────┘
```

---

## 🧠 RAG Pipeline

```
Full Page Text (cleaned, noise removed)
      │
      ▼
RecursiveCharacterTextSplitter  (500 chars, 50 overlap)
      │
      ▼
For each chunk → SHA256 hash
      ├── Hash in SQLite?  → fetch cached embedding  ⚡
      └── Not cached?      → embed with all-MiniLM-L6-v2 → store
      │
      ▼
User Query → embed → cosine similarity vs all chunk embeddings
      │
      ▼
Top K most relevant chunks selected
      │
      ▼
LLM receives only the relevant chunks (~1500 chars)
      │
      ▼
Answer + best source re-ranked by similarity to the answer
```

---

## 📁 Project Structure

```
browser-aware-ai-assistant/
│
├── backend/
│   ├── main.py              # FastAPI app — all endpoints
│   ├── rag_service.py       # RAG pipeline with SQLite embedding cache
│   ├── llm_service.py       # LLM call wrapper (plug in any LLM)
│   ├── price_service.py     # Price recording & history
│   ├── youtube_service.py   # Transcript fetching & chunking
│   ├── youtube_rag.py       # YouTube-specific RAG with timestamps
│   ├── models.py            # Pydantic request/response models
│   ├── rag_cache.db         # Auto-created: chunk embedding cache
│   └── prices.db            # Auto-created: price history
│
└── chrome-extension/
    ├── manifest.json
    ├── background.js        # Icon click → inject content.js
    ├── content.js           # Main extension logic
    ├── chat.html            # Chat window HTML template
    ├── chat.css             # Chat window styles
    ├── highlighter.js       # Source text highlighting on page
    ├── price_tracker.js     # Price panel logic
    ├── price_tracker.html   # Price panel HTML template
    ├── price_tracker.css    # Price panel styles
    ├── youtube_chat.js      # YouTube transcript Q&A
    └── marked.min.js        # Markdown renderer (bundled locally)
```

---

## 🚀 Setup & Installation

### 1. Clone the repository

```bash
git clone https://github.com/MeetGJethva/browser-aware-ai-assistant.git
cd browser-aware-ai-assistant
```

### 2. Install Python dependencies

```bash
pip install fastapi uvicorn httpx playwright \
            langchain langchain-community \
            sentence-transformers \
            scikit-learn numpy \
            youtube-transcript-api \
            pydantic
```

### 3. Install Playwright browsers

```bash
playwright install chromium
```

### 4. Configure your LLM

Open `backend/llm_service.py` and wire up your LLM of choice:

```python
def get_answer(context: str, query: str) -> str:
    # context = relevant page chunks from RAG
    # query   = user question
    # return  = answer string
    ...
```

Compatible with OpenAI, Anthropic, Ollama, Groq, or any local model.

### 5. Start the backend

```bash
cd browser-assistant
uv run main.py
```

Server starts at `http://127.0.0.1:8090`. Both SQLite databases are created automatically on first run.

### 6. Install the Chrome Extension

1. Open Chrome and navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top right)
3. Click **Load unpacked**
4. Select the `chrome-extension/` folder
5. Pin the extension via the 🧩 puzzle icon in your toolbar

### 7. Allow localhost connections

Chrome blocks HTTP requests from HTTPS pages by default. Fix it once:

```
chrome://flags/#block-insecure-private-network-requests
```

Set to **Disabled** and relaunch Chrome.

---

## 🖼️ How to Use

### 💬 Chat with any page

1. Visit any website
2. Click the 🤖 extension icon in the toolbar
3. The floating chat window appears on the page
4. Type your question and press **Enter**

The extension extracts clean text from the page, sends it through the RAG pipeline, and returns an answer based only on the most relevant sections — never hitting LLM token limits.

### 🔍 Source Highlighting

- Every AI response shows a **🔍 Show source** button
- Click it — the exact text the AI used gets highlighted in purple on the page
- Click again to clear the highlight
- Only one highlight active at a time; switching messages auto-clears the previous one

### 📈 Price Tracking

- Visit any product page (Amazon, Flipkart, etc.)
- Click **📈** in the chat header
- The panel shows: current price, lowest / highest / average, trend indicator, and a full price history sparkline chart
- Every visit to the same product URL automatically records the price — building history over time with zero effort

### 📺 YouTube Q&A with Timestamps

- Open any YouTube video that has captions enabled
- Open the extension — the transcript loads automatically in the background
- Ask questions like _"What does he say about gradient descent?"_
- The AI answers and shows **▶ 4:32** clickable timestamp chips
- Click any chip to jump the video to that exact moment

---

## 📡 API Reference

### `POST /chat`

```json
// Request
{
  "message": "What is this article about?",
  "context": "<full cleaned page text from extension>"
}

// Response
{
  "answer": "This article discusses...",
  "sources": ["chunk 1 text...", "chunk 2 text...", "chunk 3 text..."],
  "best_source_idx": 1
}
```

### `POST /track-price`

```json
// Request
{
  "url": "https://www.amazon.in/dp/B09XYZ",
  "title": "Product Name",
  "price": "₹12,999",
  "image_url": "https://..."
}
```

### `GET /price-history?url=<url>`

```json
// Response
{
  "success": true,
  "current": 12999,
  "lowest": 10999,
  "highest": 14999,
  "average": 12500,
  "trend": "down",
  "data_points": 8,
  "history": [
    { "price": 14999, "date": "2024-01-15 10:30:00" },
    { "price": 12999, "date": "2024-03-20 14:22:00" }
  ]
}
```

### `POST /youtube/load`

```json
// Request
{ "url": "https://www.youtube.com/watch?v=VIDEO_ID" }

// Response
{
  "success": true,
  "video_id": "VIDEO_ID",
  "total_chunks": 42,
  "total_duration": "1:12:34",
  "message": "Loaded 42 transcript chunks ✓"
}
```

### `POST /youtube/chat`

```json
// Request
{
  "video_id": "VIDEO_ID",
  "message": "What does the speaker say about overfitting?"
}

// Response
{
  "answer": "Around 14:20, the speaker explains that overfitting occurs when...",
  "timelines": [
    { "label": "14:20", "start_time": 860.0, "text": "...overfitting occurs when...", "score": 0.91 },
    { "label": "28:45", "start_time": 1725.0, "text": "...regularization prevents...", "score": 0.76 }
  ]
}
```

---

## 🛠️ Tech Stack

| Component           | Technology                                                        |
| ------------------- | ----------------------------------------------------------------- |
| Backend framework   | FastAPI + Uvicorn                                                 |
| Embeddings          | `sentence-transformers` — `all-MiniLM-L6-v2` (runs fully locally) |
| Embedding cache     | SQLite with SHA256 hash deduplication                             |
| Price storage       | SQLite                                                            |
| Text splitting      | LangChain `RecursiveCharacterTextSplitter`                        |
| Similarity search   | `scikit-learn` cosine similarity                                  |
| YouTube transcripts | `youtube-transcript-api` (no API key required)                    |
| Browser extension   | Vanilla JS — Chrome Manifest V3                                   |
| Markdown rendering  | `marked.js` (bundled locally, no CDN)                             |

---

## 🔒 Privacy

- All page content processed **locally** — nothing sent to any third party
- Embeddings and price data stored in SQLite files on your own machine
- YouTube transcripts fetched directly from YouTube — no API key needed
- Your LLM is called via your own credentials — the extension never touches them

---

## ⚠️ Known Limitations

- YouTube Q&A requires videos with closed captions / subtitles enabled
- Price auto-detection works best on Amazon and Flipkart; may miss prices on custom storefronts
- Source highlighting may not locate text inside heavily JS-rendered or shadow DOM elements
- Some websites (Google, Chrome Web Store) block extension script injection entirely

---

## 🤝 Contributing

Pull requests are welcome. For major changes please open an issue first to discuss what you would like to change.

```bash
# 1. Fork the repo
# 2. Create your branch
git checkout -b feature/my-feature

# 3. Commit your changes
git commit -m "Add my feature"

# 4. Push and open a Pull Request
git push origin feature/my-feature
```

---

## 📄 License

free to use, modify, and distribute.

---

<div align="center">

⭐ **Star this repo if you found it useful!**

**[github.com/MeetGJethva/browser-aware-ai-assistant](https://github.com/MeetGJethva/browser-aware-ai-assistant)**

Built with ❤️ using RAG • SQLite • FastAPI • Chrome Extensions • SentenceTransformers

</div>
