import json
from sqlmodel import Session, select
from database import engine, Item, SearchSession, SearchItemLink, ExtractionSchema
from llm_core import get_llm_provider
from llm_engine import summarize_search_results, extract_specs, decide_action

class ProcessingService:
    def __init__(self):
        self.llm = get_llm_provider()

    async def process_incoming_data(self, task_id: int, raw_items: list, is_deep_analysis: bool = False):
        with Session(engine) as session:
            search_request = session.get(SearchSession, task_id)
            if not search_request: return

            processed_items = []
            for item_dto in raw_items:
                try:
                    existing_item = session.exec(select(Item).where(Item.url == item_dto.url)).first()
                    if not existing_item:
                        db_item = Item(
                            url=item_dto.url, title=item_dto.title, price=item_dto.price,
                            description=item_dto.description, image_path=item_dto.local_path,
                            raw_json=json.dumps(item_dto.model_dump(), default=str)
                        )
                        session.add(db_item); session.commit(); session.refresh(db_item)
                        
                        # Извлечение характеристик (здесь идет нагрузка на ПК)
                        try:
                            specs = await extract_specs(db_item.title, db_item.description or "", db_item.price, db_item.image_path)
                            db_item.structured_data = json.dumps(specs, ensure_ascii=False)
                            session.add(db_item); session.commit()
                        except: pass
                    else:
                        db_item = existing_item

                    processed_items.append(db_item)
                    if not session.exec(select(SearchItemLink).where(SearchItemLink.search_id==task_id, SearchItemLink.item_id==db_item.id)).first():
                        session.add(SearchItemLink(search_id=task_id, item_id=db_item.id))
                        session.commit()
                except: continue

            # Генерация отчета
            if processed_items:
                res = await summarize_search_results(search_request.query_text, processed_items)
                search_request.summary = res.get("summary")
                search_request.reasoning = res.get("reasoning")
            
            search_request.status = "done"
            session.add(search_request); session.commit()

class ChatProcessingService:
    async def process_user_message(self, user_message: str, chat_history: list):
        try:
            decision = await decide_action(chat_history, [])
            return {"decision": decision}
        except:
            return {"decision": {"action": "chat", "reply": "Ошибка LLM"}}