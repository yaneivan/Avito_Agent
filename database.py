from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
import os

# Создаем папку для данных, если её нет
os.makedirs("./data", exist_ok=True)

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/avito_agent.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


class DBMarketResearch(Base):
    __tablename__ = "market_research"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, index=True)
    chat_history = Column(Text)  # JSON history as text
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DBSchema(Base):
    __tablename__ = "schemas"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text)
    json_schema = Column(Text)  # JSON schema as text
    created_at = Column(DateTime, default=datetime.utcnow)


class DBRawLot(Base):
    __tablename__ = "raw_lots"

    id = Column(Integer, primary_key=True, index=True)
    url = Column(String, unique=True, index=True)
    title = Column(String)
    price = Column(String)
    description = Column(Text)
    image_path = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DBAnalyzedLot(Base):
    __tablename__ = "analyzed_lots"

    id = Column(Integer, primary_key=True, index=True)
    raw_lot_id = Column(Integer, ForeignKey("raw_lots.id"))
    search_task_id = Column(Integer)
    schema_id = Column(Integer, ForeignKey("schemas.id"))
    structured_data = Column(Text)
    relevance_note = Column(Text)
    image_description_and_notes = Column(Text)
    tournament_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class DBSearchTask(Base):
    __tablename__ = "search_tasks"

    id = Column(Integer, primary_key=True, index=True)
    market_research_id = Column(Integer, ForeignKey("market_research.id"))
    mode = Column(String)  # "quick" or "deep"
    topic = Column(String) 
    query = Column(String)
    schema_id = Column(Integer, ForeignKey("schemas.id"), nullable=True)
    needs_visual = Column(Boolean, default=False)
    limit = Column(Integer, default=10)  # Количество товаров для поиска
    status = Column(String, default="pending")  # "pending", "in_progress", "completed", "failed"
    results = Column(Text, nullable=True)  # JSON results as text
    created_at = Column(DateTime, default=datetime.utcnow)


# Создаем таблицы
Base.metadata.create_all(bind=engine)