from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum


class State(str, Enum):
    CHAT = "CHAT"
    SEARCHING_QUICK = "SEARCHING_QUICK"
    PLANNING_DEEP_RESEARCH = "PLANNING_DEEP_RESEARCH"
    DEEP_RESEARCH = "DEEP_RESEARCH"


class ChatMessage(BaseModel):
    id: Optional[str] = None  # Unique identifier for the message
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = datetime.now()
    images: Optional[List[str]] = []  # Base64 encoded images
    items: Optional[List[dict]] = []  
    task_id: Optional[int] = None  


class Schema(BaseModel):
    id: Optional[int] = None
    name: str
    description: str
    json_schema: dict  # JSON schema for structured outputs


class RawLot(BaseModel):
    id: Optional[int] = None
    url: str
    title: str
    price: str
    description: str
    image_path: Optional[str] = None  # Path to saved image
    created_at: datetime = datetime.now()


class AnalyzedLot(BaseModel):
    id: Optional[int] = None
    raw_lot_id: int
    search_task_id: int  
    schema_id: int
    structured_data: dict
    relevance_note: str
    image_description_and_notes: str
    tournament_score: float = 0.0
    created_at: datetime = datetime.now()

class SearchTask(BaseModel):
    id: Optional[int] = None
    market_research_id: int
    mode: str  # "quick" or "deep"
    query: str
    topic: str 
    schema_id: Optional[int] = None  # For deep research
    needs_visual: bool = False
    limit: int = 10  # Количество товаров для поиска
    status: str = "pending"  # "pending", "in_progress", "completed", "failed"
    results: Optional[List[dict]] = []
    created_at: datetime = datetime.now()


class MarketResearch(BaseModel):
    id: Optional[int] = None
    state: State = State.CHAT
    chat_history: List[ChatMessage] = []
    search_tasks: List[SearchTask] = []
    created_at: datetime = datetime.now()
    updated_at: datetime = datetime.now()