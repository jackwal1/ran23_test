from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class kpiReadoutRequest(BaseModel):
    aoi: str
    engineer: str

class queryRequest(BaseModel):
    user_question: str

class ChatRequest(BaseModel):
    thread_id: str = Field(..., description="Unique identifier for the chat thread")
    message: str = Field(..., description="User message")

class SupervisorChatRequest(BaseModel):
    thread_id: str = Field(..., description="Unique identifier for the chat thread")
    message: str = Field(..., description="User message")
    user_id: Optional[str] = Field(None, description="User id")

class ChatResponse(BaseModel):
    response: str


class ClassifyQueryResponse(BaseModel):
    classification: Optional[str]
    params: Optional[Dict[str, Optional[Any]]] = None

class AutomationChatResponse(BaseModel):
    thread_id: str
    params: Optional[Dict[str, Optional[str]]] = None

class ClassifierChatRequest(BaseModel):
    thread_id: str = Field(..., description="Unique identifier for the chat thread")
    db_thread_id: str = Field(..., description="Unique identifier for common conversation thread")
    message: str = Field(..., description="User message")


class EmailRequest(BaseModel):
    email: str

class AoiResponse(BaseModel):
    status: str  # Either "success" or "fail"
    message: str  # Success message or error description
    total_count:  Optional[int]= None
    aoi: Optional[List[str]] = None  # Only present in success responses
    engineer: Optional[str] = None  # Only present in success responses

class kpiReadoutDataCollectionRequest(BaseModel):
    aoi: str
    engineer: str


class kpiReadoutDataCollectionResponse(BaseModel):
    """Response model for KPI data collection endpoint"""
    key: str
    message: str
    status: str

class kpiReadoutAnalysisRequest(BaseModel):
    """Request model for KPI analysis endpoint"""
    key: str
