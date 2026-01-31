import json
from sqlmodel import Session, select, desc
from database import DeepResearchSession, SearchSession, ChatSession, ChatMessage, ExtractionSchema
from llm_engine import deep_research_agent


# Функция для подтверждения схемы, используемая в router
async def confirm_search_schema(research_id: int, schema_dict: dict, session: Session, search_query: str):
    """Подтверждение схемы и подготовка к поиску"""
    research_session = session.get(DeepResearchSession, research_id)
    if not research_session:
        return False

    schema_str = json.dumps(schema_dict, ensure_ascii=False)
    research_session.schema_agreed = schema_str
    # Не устанавливаем stage в "parsing" сразу, а оставляем для дальнейшей обработки
    # когда будут получены результаты от расширения
    research_session.stage = "schema_confirmed"  # Новое состояние
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
    else:
        # Обновляем существующую схему новыми данными
        existing_schema.structure_json = schema_str
        session.add(existing_schema)
        session.commit()
        research_session.schema_id = existing_schema.id

    session.add(research_session)
    session.commit()

    # Создаем связанную SearchSession для расширения
    search_session = SearchSession(
        query_text=search_query,
        status="confirmed",  # Устанавливаем статус confirmed, чтобы задача была доступна для расширения
        mode="deep_research",  # Указываем режим глубокого исследования
        stage="parsing",
        limit_count=research_session.limit_count,
        open_in_browser=research_session.open_in_browser,
        use_cache=research_session.use_cache,
        deep_research_session_id=research_session.id,  # Связываем с DeepResearchSession
        schema_id=research_session.schema_id  # Используем обновленный schema_id
    )

    session.add(search_session)
    session.commit()
    session.refresh(search_session)  # Обновляем, чтобы получить ID

    return True