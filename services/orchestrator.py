import json
from sqlmodel import Session, select, desc
from database import DeepResearchSession, SearchSession, ChatSession, ChatMessage, ExtractionSchema
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

    def _get_or_create_search_session(self, query: str) -> DeepResearchSession:
        """Устаревший метод"""
        s = self.db.exec(select(DeepResearchSession).where(DeepResearchSession.status == "created").order_by(desc(DeepResearchSession.created_at))).first()
        if not s:
            print("[DEBUG ORCH] Creating new Deep Research Session")
            s = DeepResearchSession(query_text=query, stage="interview", status="created", limit_count=10)
            self.db.add(s); self.db.commit(); self.db.refresh(s)
        return s

    def _get_or_create_chat_session(self, research_session: DeepResearchSession) -> ChatSession:
        """Устаревший метод"""
        # Проверяем, есть ли уже связанная чат-сессия
        if research_session.chat_session_id:
            c = self.db.get(ChatSession, research_session.chat_session_id)
            if c:
                return c
        
        # Создаем новую чат-сессию
        title = f"Глубокое исследование: {research_session.query_text[:30]}..."
        c = ChatSession(title=title)
        self.db.add(c); self.db.commit(); self.db.refresh(c)
        
        # Связываем сессии
        research_session.chat_session_id = c.id
        self.db.add(research_session); self.db.commit()
        
        return c

    def _save_message(self, chat_id: int, role: str, content: str, meta: dict):
        """Устаревший метод"""
        msg = ChatMessage(role=role, content=content, chat_session_id=chat_id, extra_metadata=json.dumps(meta, ensure_ascii=False))
        self.db.add(msg); self.db.commit()

    async def confirm_schema(self, research_id: int, schema_str: str):
        """Устаревший метод"""
        print(f"[DEBUG ORCH] Confirming schema for Research #{research_id}")
        s = self.db.get(DeepResearchSession, research_id)
        if not s: return None
        s.schema_agreed, s.stage, s.status = schema_str, "parsing", "confirmed"

        name = f"DeepResearch_{s.id}"
        ex = self.db.exec(select(ExtractionSchema).where(ExtractionSchema.name == name)).first()
        if not ex:
            ex = ExtractionSchema(name=name, description="Auto", structure_json=schema_str)
            self.db.add(ex); self.db.commit(); self.db.refresh(ex)
        s.schema_id = ex.id
        self.db.add(s); self.db.commit();


# Функция для подтверждения схемы, используемая в router
async def confirm_search_schema(research_id: int, schema_dict: dict, session: Session):
    """Подтверждение схемы и подготовка к поиску"""
    research_session = session.get(DeepResearchSession, research_id)
    if not research_session:
        return False

    schema_str = json.dumps(schema_dict, ensure_ascii=False)
    research_session.schema_agreed = schema_str
    research_session.stage = "parsing"
    research_session.status = "confirmed"

    # Создаем или обновляем схему извлечения
    name = f"DeepResearch_{research_session.id}"
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
        research_session.schema_id = new_schema.id

    session.add(research_session)
    session.commit()

    # Создаем связанную SearchSession для расширения
    search_session = SearchSession(
        query_text=research_session.query_text,
        status="confirmed",  # Устанавливаем статус confirmed, чтобы задача была доступна для расширения
        mode="deep_research",  # Указываем режим глубокого исследования
        stage="parsing",
        limit_count=research_session.limit_count,
        open_in_browser=research_session.open_in_browser,
        use_cache=research_session.use_cache,
        deep_research_session_id=research_session.id,  # Связываем с DeepResearchSession
        schema_id=new_schema.id if not existing_schema else existing_schema.id  # Используем ту же схему
    )

    session.add(search_session)
    session.commit()
    session.refresh(search_session)  # Обновляем, чтобы получить ID

    return True