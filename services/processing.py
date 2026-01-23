import json
import traceback
from sqlmodel import Session, select
from database import engine, Item, SearchSession, SearchItemLink
from llm_engine import evaluate_relevance, rank_items_group, summarize_search_results

class ProcessingService:
    async def process_incoming_data(self, task_id: int, raw_items: list, is_deep_analysis: bool = False):
        print(f"\n[DEBUG SERVICE] Processing Task #{task_id}. Items received: {len(raw_items)}")
        
        with Session(engine) as session:
            s_req = session.get(SearchSession, task_id)
            if not s_req:
                print(f"[ERROR SERVICE] Task #{task_id} not found in DB!")
                return

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
                        vlm = await evaluate_relevance(
                            db_item.title, db_item.description or "", db_item.price, 
                            db_item.image_path or "", s_req.query_text
                        )
                        
                        db_item.relevance_score = vlm.get("relevance_score", 1)
                        db_item.visual_notes = vlm.get("visual_notes", "")
                        db_item.structured_data = json.dumps(vlm.get("specs", {}), ensure_ascii=False)
                        
                        session.add(db_item)
                        session.commit()
                    
                    print(f"[DEBUG SERVICE] Item {i} Score: {db_item.relevance_score}")

                    # ВРЕМЕННО: Пропускаем всё с score >= 1 (было > 0), чтобы отсеять совсем мусор, но не переборщить
                    if db_item.relevance_score >= 1:
                        processed_items.append(db_item)
                        # Линкуем
                        if not session.exec(select(SearchItemLink).where(SearchItemLink.search_id==task_id, SearchItemLink.item_id==db_item.id)).first():
                            session.add(SearchItemLink(search_id=task_id, item_id=db_item.id))
                            session.commit()
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

            s_req.status = "done"
            if is_deep_analysis: s_req.stage = "completed"
            
            session.add(s_req)
            session.commit()
            print(f"[DEBUG SERVICE] Task #{task_id} DONE. Summary saved.")

class ChatProcessingService:
    async def process_user_message(self, user_message: str, chat_history: list):
        from llm_engine import decide_action
        try:
            return {"decision": await decide_action(chat_history, [])}
        except Exception as e:
            print(f"[ERROR CHAT] {e}")
            return {"decision": {"action": "chat", "reply": "Ошибка сервиса."}}