"""
Слой бизнес-логики (Business Logic Layer) для проекта Avito Agent
"""
import json
import traceback
from typing import Dict, Any, List, Optional
from core.repositories import (
    ItemRepository, SearchSessionRepository, SearchItemLinkRepository, ExtractionSchemaRepository
)
from database import SearchSession, DeepResearchSession
from llm_engine import extract_product_features, rank_items_group, summarize_search_results


class ItemProcessingService:
    """Сервис для обработки товаров"""

    @staticmethod
    async def process_single_item(item_data: Any, search_request: Any, extraction_schema: Optional[Dict] = None):
        """
        Обработка одного товара: сохранение в базу и извлечение характеристик
        """
        # Подготовка данных для сохранения
        item_db_data = {
            'url': item_data.url,
            'title': item_data.title,
            'price': item_data.price,
            'description': item_data.description,
            'image_path': item_data.local_path,
            'raw_json': json.dumps(item_data.model_dump(), default=str)
        }

        # Сохраняем товар в базу данных
        db_item = ItemRepository.create_item(item_db_data)

        # Выполняем VLM-анализ
        vlm_result = await extract_product_features(
            db_item.title,
            db_item.description or "",
            db_item.price,
            db_item.image_path or "",
            search_request.query_text,
            extraction_schema
        )

        # Обновляем товар с результатами VLM
        if isinstance(vlm_result, dict):
            updated_item = ItemRepository.update_item(
                db_item.id,
                relevance_score=vlm_result.get("relevance_score", 1),
                visual_notes=vlm_result.get("visual_notes", ""),
                structured_data=json.dumps(vlm_result.get("specs", {}))
            )

        return updated_item


class SearchResultService:
    """Сервис для работы с результатами поиска"""

    @staticmethod
    def create_links_for_session(search_session_id: int, item_ids: List[int]):
        """Создание связей между сессией и товарами"""
        for item_id in item_ids:
            SearchItemLinkRepository.create_link(search_session_id, item_id)

    @staticmethod
    def get_items_for_session(session_id: int, session_type: str = "search") -> List[Any]:
        """Получение товаров для сессии"""
        return ItemRepository.get_items_by_session(session_id, session_type)

    @staticmethod
    def update_session_status(session_id: int, status: str, session_type: str = "search"):
        """Обновление статуса сессии"""
        SearchSessionRepository.update_session_status(session_id, status, session_type)


class ProcessingService:
    """Сервис для обработки входящих данных"""

    @staticmethod
    async def process_incoming_data(task_id: int, raw_items: list, is_deep_analysis: bool = False):
        print(f"\n[DEBUG SERVICE] Processing Task #{task_id}. Items received: {len(raw_items)}")

        # Получаем сессию из базы данных
        s_req = SearchSessionRepository.get_session_by_id(task_id, "search")
        research_session = None

        if not s_req:
            research_session = SearchSessionRepository.get_session_by_id(task_id, "deep_research")
            if not research_session:
                print(f"[ERROR SERVICE] Task #{task_id} not found in DB!")
                return
            s_req = research_session  # Используем research_session как основной объект
        else:
            # Проверяем, связана ли SearchSession с DeepResearchSession
            # (это может быть случай для простых поисков)
            if s_req.deep_research_session_id:
                research_session = SearchSessionRepository.get_session_by_id(s_req.deep_research_session_id, "deep_research")

        processed_items = []

        # Если items нет, возможно расширение ничего не нашло
        if not raw_items:
            print("[WARN SERVICE] Received empty list of items from extension.")

        for i, item_dto in enumerate(raw_items):
            try:
                # Проверяем дубликаты
                db_item = ItemRepository.get_item_by_url(item_dto.url)

                if not db_item:
                    # Создаем новый
                    db_item = ItemRepository.create_item({
                        'url': item_dto.url,
                        'title': item_dto.title,
                        'price': item_dto.price,
                        'description': item_dto.description,
                        'image_path': item_dto.local_path,
                        'raw_json': json.dumps(item_dto.model_dump(), default=str)
                    })

                    # VLM анализ (может быть долгим)
                    print(f"[DEBUG SERVICE] Analyzing Item {i}: {db_item.title[:30]}...")
                    print(f"[DEBUG SERVICE] Original structured_data from extension: {getattr(item_dto, 'structured_data', 'Not found')}")

                    # Получаем схему извлечения из сессии
                    extraction_schema = None

                    # Проверяем, является ли s_req DeepResearchSession (у него есть schema_agreed)
                    if hasattr(s_req, 'schema_agreed') and s_req.schema_agreed:
                        extraction_schema = json.loads(s_req.schema_agreed)
                        print(f"[DEBUG SERVICE] Using extraction schema from DeepResearchSession: {list(extraction_schema.keys()) if extraction_schema else 'None'}")

                    # Если s_req - это SearchSession, используем schema_id для получения схемы
                    elif hasattr(s_req, 'schema_id') and s_req.schema_id:
                        schema_obj = ExtractionSchemaRepository.get_schema_by_id(s_req.schema_id)
                        if schema_obj:
                            extraction_schema = json.loads(schema_obj.structure_json)
                            print(f"[DEBUG SERVICE] Using extraction schema from SearchSession: {list(extraction_schema.keys()) if extraction_schema else 'None'}")

                    try:
                        vlm = await extract_product_features(
                            db_item.title, db_item.description or "", db_item.price,
                            db_item.image_path or "", s_req.query_text, extraction_schema
                        )

                        # Проверяем, что vlm - это словарь, а не строка
                        if isinstance(vlm, str):
                            print(f"[ERROR SERVICE] VLM returned string instead of dict: {vlm}")
                            vlm = {}
                        print(f"[DEBUG SERVICE] VLM result: {vlm}")
                        print(f"[DEBUG SERVICE] VLM specs: {vlm.get('specs', 'No specs found') if isinstance(vlm, dict) else 'VLM result is not a dict'}")

                        # Обновляем элемент
                        specs_data = {}
                        if isinstance(vlm, dict):
                            specs_data = vlm.get("specs", {})

                        # Решаем, какие структурированные данные сохранить:
                        # 1. Если VLM вернул спецификации, используем их
                        # 2. Иначе используем оригинальные данные из расширения
                        if not specs_data and hasattr(item_dto, 'structured_data') and item_dto.structured_data:
                            print(f"[DEBUG SERVICE] Using original structured_data from extension: {item_dto.structured_data}")
                            specs_data = item_dto.structured_data
                        else:
                            print(f"[DEBUG SERVICE] Using VLM structured data: {specs_data}")

                        print(f"[DEBUG SERVICE] Saving structured data: {specs_data}")

                        ItemRepository.update_item(
                            db_item.id,
                            relevance_score=vlm.get("relevance_score", 1) if isinstance(vlm, dict) else 1,
                            visual_notes=vlm.get("visual_notes", "") if isinstance(vlm, dict) else "",
                            structured_data=json.dumps(specs_data, ensure_ascii=False)
                        )
                    except Exception as e:
                        print(f"[ERROR SERVICE] VLM analysis failed for item {db_item.title}: {e}")
                        # В случае ошибки, обновим элемент
                        # Но сохраним оригинальные structured_data из расширения
                        original_structured_data = "{}"
                        if hasattr(item_dto, 'structured_data') and item_dto.structured_data:
                            print(f"[DEBUG SERVICE] Saving original structured_data due to error: {item_dto.structured_data}")
                            original_structured_data = json.dumps(item_dto.structured_data, ensure_ascii=False)

                        ItemRepository.update_item(
                            db_item.id,
                            relevance_score=1,
                            visual_notes=f"Ошибка анализа: {str(e)}",
                            structured_data=original_structured_data
                        )

                print(f"[DEBUG SERVICE] Item {i} Score: {db_item.relevance_score}")

                # ВРЕМЕННО: Пропускаем всё с score >= 1 (было > 0), чтобы отсеять совсем мусор, но не переборщить
                if db_item.relevance_score >= 1:
                    processed_items.append(db_item)
                    # Линкуем
                    if isinstance(s_req, SearchSession):
                        # Для обычной SearchSession используем стандартную логику
                        if not SearchItemLinkRepository.link_exists(s_req.id, db_item.id):
                            SearchItemLinkRepository.create_link(s_req.id, db_item.id)
                            print(f"[DEBUG SERVICE] Created link between SearchSession {s_req.id} and Item {db_item.id}")
                        else:
                            print(f"[DEBUG SERVICE] Link already exists between SearchSession {s_req.id} and Item {db_item.id}")
                    elif isinstance(s_req, DeepResearchSession):
                        # Для DeepResearchSession находим связанные SearchSession и линкуем к ним
                        related_search_sessions = SearchSessionRepository.get_related_search_sessions(s_req.id)
                        print(f"[DEBUG SERVICE] Found {len(related_search_sessions)} related SearchSessions for DeepResearchSession {s_req.id}")

                        # Если есть связанные SearchSession, линкуем к ним
                        if related_search_sessions:
                            for search_session in related_search_sessions:
                                if not SearchItemLinkRepository.link_exists(search_session.id, db_item.id):
                                    SearchItemLinkRepository.create_link(search_session.id, db_item.id)
                                    print(f"[DEBUG SERVICE] Created link between related SearchSession {search_session.id} and Item {db_item.id}")
                                else:
                                    print(f"[DEBUG SERVICE] Link already exists between related SearchSession {search_session.id} and Item {db_item.id}")
                        else:
                            # Если нет связанных SearchSession, создадим новую
                            # Попробуем найти SearchSession, которая уже существует и связана с этим DeepResearchSession
                            # Это может быть случай, если сессия была создана ранее
                            existing_search_session = SearchSessionRepository.get_existing_search_session(s_req.id)
                            print(f"[DEBUG SERVICE] Looking for existing SearchSession for DeepResearchSession {s_req.id}, found: {existing_search_session.id if existing_search_session else 'None'}")

                            if existing_search_session:
                                # Используем существующую сессию
                                search_session = existing_search_session
                                # Связываем товар с найденной сессией
                                if not SearchItemLinkRepository.link_exists(search_session.id, db_item.id):
                                    SearchItemLinkRepository.create_link(search_session.id, db_item.id)
                                    print(f"[DEBUG SERVICE] Created link between existing SearchSession {search_session.id} and Item {db_item.id}")
                                else:
                                    print(f"[DEBUG SERVICE] Link already exists between existing SearchSession {search_session.id} and Item {db_item.id}")
                            else:
                                # Создадим новую
                                search_session = SearchSessionRepository.create_search_session_for_deep_research(
                                    s_req.query_text, s_req.id
                                )
                                print(f"[DEBUG SERVICE] Created new SearchSession {search_session.id} for DeepResearchSession {s_req.id}")

                                # Связываем товар с найденной/созданной сессией
                                if not SearchItemLinkRepository.link_exists(search_session.id, db_item.id):
                                    SearchItemLinkRepository.create_link(search_session.id, db_item.id)
                                    print(f"[DEBUG SERVICE] Created link between new SearchSession {search_session.id} and Item {db_item.id}")
                                else:
                                    print(f"[DEBUG SERVICE] Link already exists between new SearchSession {search_session.id} and Item {db_item.id}")
                else:
                    print(f"[DEBUG SERVICE] Filtered out item: {db_item.title} (Score 0)")

            except Exception as e:
                print(f"[ERROR SERVICE] Item processing failed: {e}")
                traceback.print_exc()
                continue

        print(f"[DEBUG SERVICE] Total processed valid items: {len(processed_items)}")

        # Турнир (только если товаров достаточно и режим deep)
        if is_deep_analysis and len(processed_items) > 1:
            print("[DEBUG SERVICE] Starting Tournament...")
            try:
                borda = {i.id: 0 for i in processed_items}
                for i in range(0, len(processed_items), 5):
                    group = processed_items[i:i+5]
                    if len(group) < 2: continue
                    ranks = await rank_items_group(
                        [{"id": it.id, "title": it.title, "price": it.price} for it in group],
                        s_req.query_text
                    )
                    for r in ranks.get("ranks", []):
                        borda[r['item_id']] += (6 - r['score'])
                processed_items.sort(key=lambda x: borda.get(x.id, 0), reverse=True)
            except Exception as e:
                print(f"[ERROR SERVICE] Tournament failed: {e}")

        # Генерация отчета
        s_req.summary = "Анализ завершен."
        if processed_items:
            try:
                print("[DEBUG SERVICE] Generating Summary...")
                res = await summarize_search_results(s_req.query_text, processed_items)
                s_req.summary = res.get("summary", "Отчет готов.")
                s_req.reasoning = res.get("reasoning", "")
            except Exception as e:
                print(f"[ERROR SERVICE] Summary failed: {e}")
                s_req.summary = f"Найдено {len(processed_items)} товаров, но отчет не создан из-за ошибки LLM."
        else:
            s_req.summary = "К сожалению, подходящих товаров не найдено."

        # Устанавливаем статус в зависимости от типа сессии
        if isinstance(s_req, SearchSession):
            s_req.status = "done"
            if is_deep_analysis:
                s_req.stage = "completed"
            s_req.summary = s_req.summary
            s_req.reasoning = s_req.reasoning

            # Если это часть глубокого исследования, обновим также и родительскую сессию
            if s_req.deep_research_session_id:
                dr_session = SearchSessionRepository.get_session_by_id(s_req.deep_research_session_id, "deep_research")
                if dr_session:
                    dr_session.status = "completed"
                    dr_session.stage = "completed"
                    dr_session.summary = s_req.summary
                    dr_session.reasoning = s_req.reasoning
        elif isinstance(s_req, DeepResearchSession):
            s_req.status = "completed"
            s_req.stage = "completed"
            s_req.summary = s_req.summary
            s_req.reasoning = s_req.reasoning

        print(f"[DEBUG SERVICE] Task #{task_id} DONE. Summary saved.")


class ChatProcessingService:
    """Сервис для обработки чат-сообщений"""

    @staticmethod
    async def process_user_message(user_message: str, chat_history: list):
        from llm_engine import decide_action
        try:
            return {"decision": await decide_action(chat_history)}
        except Exception as e:
            print(f"[ERROR CHAT] {e}")
            return {"decision": {"action": "chat", "reply": "Ошибка сервера."}}