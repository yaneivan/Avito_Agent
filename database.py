import os
from typing import Optional, List
from sqlmodel import Field, SQLModel, create_engine, Relationship
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class SearchItemLink(SQLModel, table=True):
    search_id: int = Field(foreign_key="searchsession.id", primary_key=True)
    item_id: int = Field(foreign_key="item.id", primary_key=True)

class ExtractionSchema(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    structure_json: str
    searches: List["SearchSession"] = Relationship(back_populates="schema_model")

class ChatSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str = Field(default="Новый чат")  # Title for the chat session
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Relationship to chat messages
    messages: List["ChatMessage"] = Relationship(back_populates="chat_session", cascade_delete=True)

class ChatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    role: str  # "user" or "assistant"
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    # Type of message (optional, for categorizing different types of responses)
    message_type: Optional[str] = None
    # Reference to the chat session this message belongs to
    chat_session_id: int = Field(foreign_key="chatsession.id")
    chat_session: Optional[ChatSession] = Relationship(back_populates="messages")
    # Additional metadata (optional)
    extra_metadata: Optional[str] = None  # JSON string for additional data

class SearchSession(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    query_text: str
    status: str = Field(default="created")  # Changed default from "pending" to "created" to prevent premature processing
    mode: str = Field(default="quick")  # Mode: "quick" or "deep"
    stage: str = Field(default="interview")  # Stage for deep mode: "interview", "schema_agreement", "parsing", "analysis", "completed"
    created_at: datetime = Field(default_factory=datetime.now)

    # Настройки
    limit_count: int = Field(default=int(os.getenv("DEFAULT_LIMIT_COUNT", "20")))
    open_in_browser: bool = Field(default=True)
    use_cache: bool = Field(default=False)

    # Результат анализа (ответ чата)
    summary: Optional[str] = None # <-- НОВОЕ ПОЛЕ
    reasoning: Optional[str] = None  # Объяснение решения LLM
    internal_thoughts: Optional[str] = None  # Внутренние размышления LLM
    interview_data: Optional[str] = None  # JSON string storing interview responses
    schema_agreed: Optional[str] = None  # JSON string storing agreed schema
    analysis_result: Optional[str] = None  # Analysis result for deep research

    schema_id: Optional[int] = Field(default=None, foreign_key="extractionschema.id")
    schema_model: Optional[ExtractionSchema] = Relationship(back_populates="searches")

    items: List["Item"] = Relationship(back_populates="searches", link_model=SearchItemLink)

class Item(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    url: str = Field(unique=True, index=True)
    title: str
    price: str
    description: Optional[str] = None
    image_path: Optional[str] = None
    raw_json: str
    structured_data: Optional[str] = None
    relevance_score: int = 0  # По умолчанию 0, будет обновлено после анализа
    visual_notes: Optional[str] = None  # Описание визуального состояния товара

    searches: List[SearchSession] = Relationship(back_populates="items", link_model=SearchItemLink)

sqlite_file_name = os.getenv("DATABASE_FILE_NAME", "database.db")
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, connect_args={"check_same_thread": False})

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)