from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from models import ChatRequest, ChatResponse
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
    # Use extension-provided context if available, else use browser_manager's
    context = data.context or ""
    answer = get_answer(context, data.message)
    return ChatResponse(answer=answer)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8090, timeout_keep_alive=60)