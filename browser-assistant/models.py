from pydantic import BaseModel


class URLRequest(BaseModel):
    url: str


class ChatResponse(BaseModel):
    answer: str
    

class ChatRequest(BaseModel):
    message: str
    context: str | None = None  # page content from extension