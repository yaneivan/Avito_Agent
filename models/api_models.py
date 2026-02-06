from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
from enum import Enum
from .research_models import State, ChatMessage, Schema, RawLot, AnalyzedLot, SearchTask, MarketResearch


# Добавим модели для API запросов и ответов
class CreateMarketResearchRequest(BaseModel):
    initial_query: str


class CreateSearchTaskRequest(BaseModel):
    market_research_id: int
    mode: str  # "quick" or "deep"
    query: str
    schema_id: Optional[int] = None
    needs_visual: bool = False


class SubmitResultsRequest(BaseModel):
    task_id: int
    items: List[dict]


class GetTaskResponse(BaseModel):
    task_id: int
    query: str
    active_tab: bool = True
    limit: int = 10


class ChatUpdateRequest(BaseModel):
    message: str
    images: Optional[List[str]] = []


# Модель для турнирного реранкинга
class TournamentRankingRequest(BaseModel):
    lot_groups: List[List[dict]]  # Группы лотов для сравнения (по 5 штук)
    criteria: str  # Критерии для сравнения


class TournamentRankingResponse(BaseModel):
    ranked_lots: List[dict]  # Отсортированные лоты по рейтингу