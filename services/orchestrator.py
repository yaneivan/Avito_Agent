import json
from sqlmodel import Session, select, desc
from database import SearchSession, ChatSession, ChatMessage, ExtractionSchema
from llm_engine import deep_research_agent

class DeepResearchOrchestrator:
    """
    Устаревший класс. Оставлен для обратной совместимости.
    Основная логика теперь находится в routers/deep_research.py
    """

    def __init__(self, session: Session):
        self.db = session

    async def handle_message(self, chat_history: list, user_content: str):
        """
        Устаревший метод. Используйте llm_engine.deep_research_agent напрямую.
        """
        # Этот метод оставлен для обратной совместимости,
        # но основная логика теперь в routers/deep_research.py
        raise NotImplementedError("Этот метод устарел. Используйте llm_engine.deep_research_agent напрямую.")

    def _get_or_create_search_session(self, query: str) -> SearchSession:
        """Устаревший метод"""
        s = self.db.exec(select(SearchSession).where(SearchSession.mode == "deep", SearchSession.status == "created").order_by(desc(SearchSession.created_at))).first()
        if not s:
            print("[DEBUG ORCH] Creating new Deep Session")
            s = SearchSession(query_text=query, mode="deep", stage="interview", status="created", limit_count=10)
            self.db.add(s); self.db.commit(); self.db.refresh(s)
        return s

    def _get_or_create_chat_session(self, search_id: int) -> ChatSession:
        """Устаревший метод"""
        title = f"Deep Research Chat - {search_id}"
        c = self.db.exec(select(ChatSession).where(ChatSession.title.contains(str(search_id)))).first()
        if not c:
            c = ChatSession(title=title)
            self.db.add(c); self.db.commit(); self.db.refresh(c)
        return c

    def _save_message(self, chat_id: int, role: str, content: str, meta: dict):
        """Устаревший метод"""
        msg = ChatMessage(role=role, content=content, chat_session_id=chat_id, extra_metadata=json.dumps(meta, ensure_ascii=False))
        self.db.add(msg); self.db.commit()

    async def confirm_schema(self, search_id: int, schema_str: str):
        """Устаревший метод"""
        print(f"[DEBUG ORCH] Confirming schema for Task #{search_id}")
        s = self.db.get(SearchSession, search_id)
        if not s: return None
        s.schema_agreed, s.stage, s.status = schema_str, "parsing", "confirmed"

        name = f"DeepResearch_{s.id}"
        ex = self.db.exec(select(ExtractionSchema).where(ExtractionSchema.name == name)).first()
        if not ex:
            ex = ExtractionSchema(name=name, description="Auto", structure_json=schema_str)
            self.db.add(ex); self.db.commit(); self.db.refresh(ex)
        s.schema_id = ex.id
        self.db.add(s); self.db.commit()


# Функция для подтверждения схемы, используемая в router
async def confirm_search_schema(search_id: int, schema_dict: dict, session: Session):
    """Подтверждение схемы и подготовка к поиску"""
    search_session = session.get(SearchSession, search_id)
    if not search_session:
        return False

    schema_str = json.dumps(schema_dict, ensure_ascii=False)
    search_session.schema_agreed = schema_str
    search_session.stage = "parsing"
    search_session.status = "confirmed"

    # Создаем или обновляем схему извлечения
    name = f"DeepResearch_{search_session.id}"
    existing_schema = session.exec(
        select(ExtractionSchema).where(ExtractionSchema.name == name)
    ).first()

    if not existing_schema:
        new_schema = ExtractionSchema(
            name=name,
            description="Auto-generated schema for deep research",
            structure_json=schema_str
        )
        session.add(new_schema)
        session.commit()
        session.refresh(new_schema)
        search_session.schema_id = new_schema.id

    session.add(search_session)
    session.commit()

    return True