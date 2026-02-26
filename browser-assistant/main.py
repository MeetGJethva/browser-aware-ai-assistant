from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, ChatResponse
from rag_service import process_page_and_query
from llm_service import get_answer
from price_service import record_price, get_price_history
from pydantic import BaseModel
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
    relevant_context = process_page_and_query(
        page_content=raw_context,
        query=data.message,
        top_k=10
    )
    print(f"[CHAT] Sending {len(relevant_context)} chars of context to LLM")
    answer = get_answer(relevant_context, data.message)
    return ChatResponse(answer=answer)


# ── Price Tracking ──────────────────────────────────────────────────────────

class PriceTrackRequest(BaseModel):
    url:       str
    title:     str
    price:     str        # raw string like "₹1,23,456"
    image_url: str = ""

class PriceHistoryRequest(BaseModel):
    url: str


@app.post("/track-price")
async def track_price(data: PriceTrackRequest):
    result = record_price(data.url, data.title, data.price, data.image_url)
    return result


@app.get("/price-history")
async def price_history(url: str):
    result = get_price_history(url)
    return result


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090, timeout_keep_alive=60)