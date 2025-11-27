from pydantic import BaseModel, Field
from typing import Optional, Dict, Any

class queryRequest(BaseModel):
    user_question: str

class ChatRequest(BaseModel):
    thread_id: str = Field(..., description="Unique identifier for the chat thread")
    message: str = Field(..., description="User message")

class ChatResponse(BaseModel):
    response: str


class ClassifyQueryResponse(BaseModel):
    classification: str
    params: Optional[Dict[str, Optional[Any]]] = None

class AutomationChatResponse(BaseModel):
    thread_id: str
    params: Optional[Dict[str, Optional[str]]] = None
