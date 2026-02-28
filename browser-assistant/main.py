from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, ChatResponse
from rag_service import process_page_and_query
from llm_service import get_answer
from price_service import record_price, get_price_history
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
    return ChatResponse(answer=answer, sources=source_chunks)


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


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090, timeout_keep_alive=60)