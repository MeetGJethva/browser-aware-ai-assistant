from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, ChatResponse
from rag_service import process_page_and_query
from llm_service import get_answer
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
    # Get raw page content — from extension or browser_manager
    raw_context = data.context or ""

    if not raw_context.strip():
        return ChatResponse(answer="I couldn't read any content from this page.")

    # RAG pipeline: chunk → hash check → embed → retrieve top 3
    relevant_context = process_page_and_query(
        page_content=raw_context,
        query=data.message,
        top_k=10
    )
    print(relevant_context)
    print(f"[CHAT] Sending {len(relevant_context)} chars of context to LLM")

    answer = get_answer(relevant_context, data.message)
    return ChatResponse(answer=answer)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090, timeout_keep_alive=60)