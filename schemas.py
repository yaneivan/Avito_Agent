from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ItemSchema(BaseModel):
    title: str
    price: str
    url: str
    description: Optional[str] = None
    image_base64: Optional[str] = None
    local_path: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None 

class SubmitData(BaseModel):
    task_id: int
    items: List[ItemSchema]

class ChatRequest(BaseModel):
    history: List[Dict[str, Any]]
    open_browser: bool = True
    use_cache: bool = True

class DeepResearchRequest(BaseModel):
    history: List[Dict[str, Any]]
    agreed_schema: Optional[str] = None

class InterviewRequest(BaseModel):
    history: List[Dict[str, Any]]
    research_session_id: Optional[int] = None
    chat_id: Optional[int] = None

class SchemaAgreementRequest(BaseModel):
    search_id: int
    agreed_schema: str | dict

class SqlGenerationRequest(BaseModel):
    search_id: int
    criteria: str

class LogMessage(BaseModel):
    source: str
    message: str
    level: str = "info"

class ChatMessageSchema(BaseModel):
    role: str
    content: str
    message_type: Optional[str] = "text"
    extra_metadata: Optional[str] = None

class RelevanceEvaluation(BaseModel):
    relevance_score: int
    visual_notes: str
    specs: dict = {}