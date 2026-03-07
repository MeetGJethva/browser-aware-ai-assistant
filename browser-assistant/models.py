from pydantic import BaseModel


class URLRequest(BaseModel):
    url: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[str] = []
    best_source_idx: int = 0 
    

class ChatRequest(BaseModel):
    message: str
    context: str | None = None  # page content from extension