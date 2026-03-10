from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, ChatResponse, SummarizeRequest, SummarizeResponse
from rag_service import process_page_and_query, find_best_source
from llm_service import get_answer
from price_service import record_price, get_price_history
from gdocs_service import create_google_doc
from youtube_service import extract_video_id, fetch_transcript, build_timed_chunks, format_timestamp
from youtube_rag import store_youtube_chunks, query_youtube
from pydantic import BaseModel
import httpx
import re
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/chat", response_model=ChatResponse)
async def chat(data: ChatRequest):
    raw_context = data.context or ""
    if not raw_context.strip():
        return ChatResponse(answer="I couldn't read any content from this page.")
    relevant_context, source_chunks = process_page_and_query(
        page_content=raw_context,
        query=data.message,
        top_k=10
    )
    print(f"[CHAT] Sending {len(relevant_context)} chars of context to LLM")
    answer = get_answer(relevant_context, data.message)
    best_idx = find_best_source(answer, source_chunks)
    for s in source_chunks:
        print(f"Sources: {s}")
    print(f"\nBest source: {source_chunks[best_idx]}")
    return ChatResponse(answer=answer, sources=source_chunks, best_source_idx=best_idx)  # ← return sources


# ── Price Tracking ──────────────────────────────────────────────────────────

class PriceTrackRequest(BaseModel):
    url: str
    title: str
    price: str
    image_url: str = ""

@app.post("/track-price")
async def track_price(data: PriceTrackRequest):
    return record_price(data.url, data.title, data.price, data.image_url)

@app.get("/price-history")
async def price_history(url: str):
    return get_price_history(url)


# ── YouTube ─────────────────────────────────────────────────────────────────

class YouTubeLoadRequest(BaseModel):
    url: str

class YouTubeChatRequest(BaseModel):
    video_id: str
    message:  str


@app.post("/youtube/load")
async def youtube_load(data: YouTubeLoadRequest):
    """Extract transcript, chunk it, embed & store. Called when user opens YT video."""
    video_id = extract_video_id(data.url)
    print(f"Video Id : {video_id}")
    if not video_id:
        return {"success": False, "error": "Not a valid YouTube URL"}

    transcript = fetch_transcript(video_id)
    if not transcript:
        return {
            "success": False,
            "error": "No captions available for this video. Try a video with CC enabled."
        }

    chunks = build_timed_chunks(transcript, chunk_size=30)
    store_youtube_chunks(video_id, chunks)

    total_duration = format_timestamp(chunks[-1]["end_time"]) if chunks else "0:00"

    return {
        "success":        True,
        "video_id":       video_id,
        "total_chunks":   len(chunks),
        "total_duration": total_duration,
        "message":        f"Loaded {len(chunks)} transcript chunks ✓"
    }


@app.post("/youtube/chat")
async def youtube_chat(data: YouTubeChatRequest):
    """Answer a question about a YouTube video using timed transcript chunks."""
    top_chunks = query_youtube(data.video_id, data.message, top_k=10)
    print(f"Query : {data.message} \n\nTop Message: {top_chunks}")
    if not top_chunks:
        return {
            "answer":    "I don't have the transcript for this video loaded yet.",
            "timelines": []
        }

    # Build context with timestamps embedded
    context_parts = []
    for chunk in top_chunks:
        context_parts.append(f"[{chunk['ts_label']}] {chunk['text']}")
    context = "\n\n".join(context_parts)

    # Ask LLM
    prompt = f"""You are answering questions about a YouTube video based on its transcript.
The transcript excerpts below include timestamps in [MM:SS] format.
When answering, mention the relevant timestamps naturally.

Transcript excerpts:
{context}

Question: {data.message}"""

    answer = get_answer("", prompt)   # pass prompt directly as message

    # Build timeline markers
    timelines = [
        {
            "label":      chunk["ts_label"],
            "start_time": chunk["start_time"],
            "text":       chunk["text"][:80] + "..." if len(chunk["text"]) > 80 else chunk["text"],
            "score":      chunk["score"],
        }
        for chunk in top_chunks
    ]

    return {"answer": answer, "timelines": timelines}


# ── YouTube Summarize to Google Docs ────────────────────────────────────────

class YouTubeSummarizeRequest(BaseModel):
    video_id:    str
    video_title: str = "YouTube Video"
    video_url:   str = ""

@app.post("/youtube/summarize-to-gdocs")
async def youtube_summarize_to_gdocs(data: YouTubeSummarizeRequest):
    """Summarize a YouTube video transcript and save it as a Google Doc."""
    # Fetch broad top-k chunks to cover the whole video
    top_chunks = query_youtube(data.video_id, "summarize the full video", top_k=30)

    if not top_chunks:
        return {"summary": "⚠️ Transcript not loaded. Please click 'Load Video' first.", "doc_url": ""}

    # Build ordered transcript text (sort by start_time)
    top_chunks_sorted = sorted(top_chunks, key=lambda c: c.get("start_time", 0))
    transcript_text = "\n\n".join(
        f"[{c['ts_label']}] {c['text']}" for c in top_chunks_sorted
    )

    summarize_prompt = f"""You are an expert video content summarizer. Summarize the following YouTube video transcript clearly and concisely.

Video Title: {data.video_title}
Video URL: {data.video_url}

Transcript (with timestamps):
{transcript_text[:10000]}

Provide a well-structured summary in this format:
## Summary of: {data.video_title}

**URL:** {data.video_url}

### Overview
(2-3 sentence overview of what the video covers)

### Key Topics Covered
(Bullet list of the main topics, ideas, or segments discussed)

### Notable Insights
(2-3 standout points, quotes, or conclusions from the video)

### Conclusion
(1-2 sentence concluding remark)"""

    print(f"[YT-SUMMARIZE] Summarizing YouTube video: {data.video_title}")
    summary_text = get_answer("", summarize_prompt)

    doc_title = f"Video Summary: {data.video_title[:70]}"
    print(f"[YT-SUMMARIZE] Creating Google Doc: {doc_title}")
    doc_url = create_google_doc(doc_title, summary_text, source_url=data.video_url)
    print(f"[YT-SUMMARIZE] Doc created: {doc_url}")

    return {"summary": summary_text, "doc_url": doc_url}


# ── Summarize & Save to Google Docs ─────────────────────────────────────────

@app.post("/summarize-to-gdocs", response_model=SummarizeResponse)
async def summarize_to_gdocs(data: SummarizeRequest):
    """Summarize the full page content with LLM and save it as a Google Doc."""
    if not data.context.strip():
        return SummarizeResponse(
            summary="No page content found to summarize.",
            doc_url=""
        )

    # Build a structured summary prompt
    summarize_prompt = f"""You are an expert summarizer. Summarize the following webpage content clearly and concisely.

Page URL: {data.page_url}
Page Title: {data.page_title}

Webpage Content:
{data.context[:12000]}  

Provide a well-structured summary in this format:
## Summary of: {data.page_title}

**URL:** {data.page_url}

### Overview
(2-3 sentence overview of what the page is about)

### Key Points
(Bullet list of the most important facts, findings, or takeaways)

### Conclusion
(1-2 sentence concluding remark)"""

    print(f"[SUMMARIZE] Summarizing page: {data.page_title}")
    summary_text = get_answer("", summarize_prompt)

    # Create richly formatted Google Doc
    doc_title = f"Summary: {data.page_title[:80]}"
    print(f"[SUMMARIZE] Creating Google Doc: {doc_title}")
    doc_url = create_google_doc(doc_title, summary_text, source_url=data.page_url)
    print(f"[SUMMARIZE] Doc created: {doc_url}")

    return SummarizeResponse(summary=summary_text, doc_url=doc_url)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090, timeout_keep_alive=60)