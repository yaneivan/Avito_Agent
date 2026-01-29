import json
import traceback
from sqlmodel import Session, select
from database import engine, Item, SearchSession, DeepResearchSession, SearchItemLink
from llm_engine import extract_product_features, rank_items_group, summarize_search_results

class ProcessingService:
    async def process_incoming_data(self, task_id: int, raw_items: list, is_deep_analysis: bool = False):
        print(f"\n[DEBUG SERVICE] Processing Task #{task_id}. Items received: {len(raw_items)}")

        # Используем отдельную сессию для получения сессии
        with Session(engine) as session:
            # Определяем тип сессии: SearchSession или DeepResearchSession
            s_req = session.get(SearchSession, task_id)
            research_session = None

            if not s_req:
                research_session = session.get(DeepResearchSession, task_id)
                if not research_session:
                    print(f"[ERROR SERVICE] Task #{task_id} not found in DB!")
                    return
                s_req = research_session  # Используем research_session как основной объект
            else:
                # Проверяем, связана ли SearchSession с DeepResearchSession
                # (это может быть случай для простых поисков)
                if s_req.deep_research_session_id:
                    research_session = session.get(DeepResearchSession, s_req.deep_research_session_id)

            processed_items = []
            
            # Если items нет, возможно расширение ничего не нашло
            if not raw_items:
                print("[WARN SERVICE] Received empty list of items from extension.")

            for i, item_dto in enumerate(raw_items):
                try:
                    # Проверяем дубликаты
                    db_item = session.exec(select(Item).where(Item.url == item_dto.url)).first()
                    
                    if not db_item:
                        # Создаем новый
                        db_item = Item(
                            url=item_dto.url, title=item_dto.title, price=item_dto.price,
                            description=item_dto.description, image_path=item_dto.local_path,
                            raw_json=json.dumps(item_dto.model_dump(), default=str)
                        )
                        session.add(db_item)
                        session.commit()
                        session.refresh(db_item)
                        
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
                            from database import ExtractionSchema
                            schema_obj = session.get(ExtractionSchema, s_req.schema_id)
                            if schema_obj:
                                extraction_schema = json.loads(schema_obj.structure_json)
                                print(f"[DEBUG SERVICE] Using extraction schema from SearchSession: {list(extraction_schema.keys()) if extraction_schema else 'None'}")

                        try:
                            vlm = await extract_product_features(
                                db_item.title, db_item.description or "", db_item.price,
                                db_item.image_path or "", s_req.query_text, extraction_schema
                            )
                            print(f"[DEBUG SERVICE] VLM result: {vlm}")
                            print(f"[DEBUG SERVICE] VLM specs: {vlm.get('specs', 'No specs found')}")

                            # Обновляем элемент в отдельной транзакции, чтобы избежать блокировок
                            with Session(engine) as update_session:
                                update_item = update_session.get(Item, db_item.id)
                                if update_item:
                                    update_item.relevance_score = vlm.get("relevance_score", 1)
                                    update_item.visual_notes = vlm.get("visual_notes", "")

                                    # Решаем, какие структурированные данные сохранить:
                                    # 1. Если VLM вернул спецификации, используем их
                                    # 2. Иначе используем оригинальные данные из расширения
                                    specs_data = vlm.get("specs", {})
                                    if not specs_data and hasattr(item_dto, 'structured_data') and item_dto.structured_data:
                                        print(f"[DEBUG SERVICE] Using original structured_data from extension: {item_dto.structured_data}")
                                        specs_data = item_dto.structured_data
                                    else:
                                        print(f"[DEBUG SERVICE] Using VLM structured data: {specs_data}")

                                    print(f"[DEBUG SERVICE] Saving structured data: {specs_data}")
                                    update_item.structured_data = json.dumps(specs_data, ensure_ascii=False)
                                    update_session.add(update_item)
                                    update_session.commit()
                        except Exception as e:
                            print(f"[ERROR SERVICE] VLM analysis failed for item {db_item.title}: {e}")
                            # В случае ошибки, обновляем элемент в отдельной транзакции
                            # Но сохраняем оригинальные structured_data из расширения
                            with Session(engine) as error_session:
                                error_item = error_session.get(Item, db_item.id)
                                if error_item:
                                    error_item.relevance_score = 1
                                    error_item.visual_notes = "Ошибка анализа: " + str(e)
                                    # Сохраняем оригинальные structured_data из расширения, если они есть
                                    if hasattr(item_dto, 'structured_data') and item_dto.structured_data:
                                        print(f"[DEBUG SERVICE] Saving original structured_data due to error: {item_dto.structured_data}")
                                        error_item.structured_data = json.dumps(item_dto.structured_data, ensure_ascii=False)
                                    else:
                                        error_item.structured_data = "{}"
                                    error_session.add(error_item)
                                    error_session.commit()
                    
                    print(f"[DEBUG SERVICE] Item {i} Score: {db_item.relevance_score}")

                    # ВРЕМЕННО: Пропускаем всё с score >= 1 (было > 0), чтобы отсеять совсем мусор, но не переборщить
                    if db_item.relevance_score >= 1:
                        processed_items.append(db_item)
                        # Линкуем
                        if isinstance(s_req, SearchSession):
                            # Для обычной SearchSession используем стандартную логику
                            with Session(engine) as link_session:
                                if not link_session.exec(select(SearchItemLink).where(SearchItemLink.search_id==s_req.id, SearchItemLink.item_id==db_item.id)).first():
                                    link_session.add(SearchItemLink(search_id=s_req.id, item_id=db_item.id))
                                    link_session.commit()
                        elif isinstance(s_req, DeepResearchSession):
                            # Для DeepResearchSession создаем SearchSession и линкуем к ней
                            with Session(engine) as link_session:
                                # Создаем временную SearchSession и линкуем элемент
                                temp_search_session = SearchSession(
                                    query_text=s_req.query_text,
                                    deep_research_session_id=s_req.id,
                                    status="completed",
                                    stage="completed"
                                )
                                link_session.add(temp_search_session)
                                link_session.commit()
                                link_session.refresh(temp_search_session)

                                if not link_session.exec(select(SearchItemLink).where(SearchItemLink.search_id==temp_search_session.id, SearchItemLink.item_id==db_item.id)).first():
                                    link_session.add(SearchItemLink(search_id=temp_search_session.id, item_id=db_item.id))
                                    link_session.commit()
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
            with Session(engine) as status_session:
                if isinstance(s_req, SearchSession):
                    updated_session = status_session.get(SearchSession, s_req.id)
                    if updated_session:
                        updated_session.status = "done"
                        if is_deep_analysis:
                            updated_session.stage = "completed"
                        updated_session.summary = s_req.summary
                        updated_session.reasoning = s_req.reasoning
                        status_session.add(updated_session)
                elif isinstance(s_req, DeepResearchSession):
                    updated_session = status_session.get(DeepResearchSession, s_req.id)
                    if updated_session:
                        updated_session.status = "completed"
                        updated_session.stage = "completed"
                        updated_session.summary = s_req.summary
                        updated_session.reasoning = s_req.reasoning
                        status_session.add(updated_session)

                status_session.commit()
            print(f"[DEBUG SERVICE] Task #{task_id} DONE. Summary saved.")

class ChatProcessingService:
    async def process_user_message(self, user_message: str, chat_history: list):
        from llm_engine import decide_action
        try:
            return {"decision": await decide_action(chat_history)}
        except Exception as e:
            print(f"[ERROR CHAT] {e}")
            return {"decision": {"action": "chat", "reply": "Ошибка сервиса."}}