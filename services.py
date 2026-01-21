import json
import traceback
from sqlmodel import Session, select
from database import engine, Item, SearchSession, SearchItemLink, ExtractionSchema
from llm_core import get_llm_provider
from schema_factory import SchemaFactory
from llm_engine import summarize_search_results, extract_specs

class ProcessingService:
    def __init__(self):
        self.llm = get_llm_provider()

    async def process_incoming_data(self, task_id: int, raw_items: list, is_deep_analysis: bool = False):
        print(f"\n[DEBUG SERVICE] --- START PROCESSING TASK #{task_id} ---")

        with Session(engine) as session:
            search_request = session.get(SearchSession, task_id)
            if not search_request:
                print(f"[ERROR] Task #{task_id} not found")
                return

            # Подготовка схемы
            pydantic_model = None
            if search_request.schema_id:
                schema_record = session.get(ExtractionSchema, search_request.schema_id)
                if schema_record:
                    try:
                        struct = schema_record.structure_json
                        if isinstance(struct, str): struct = json.loads(struct)
                        if isinstance(struct, str): struct = json.loads(struct)
                        pydantic_model = SchemaFactory.create_pydantic_model(schema_record.name, struct)
                    except: pass

            processed_items_for_summary = []

            # Цикл обработки товаров
            for i, item_dto in enumerate(raw_items):
                try:
                    statement = select(Item).where(Item.url == item_dto.url)
                    existing_item = session.exec(statement).first()

                    if not existing_item:
                        db_item = Item(
                            url=item_dto.url, title=item_dto.title, price=item_dto.price,
                            description=item_dto.description, image_path=item_dto.local_path,
                            raw_json=json.dumps(item_dto.dict(), default=str)
                        )
                        session.add(db_item); session.commit(); session.refresh(db_item)

                        if pydantic_model:
                            try:
                                extracted_data = await extract_specs(
                                    title=db_item.title,
                                    desc=db_item.description or "",
                                    price=db_item.price,
                                    img_path=db_item.image_path
                                )
                                db_item.structured_data = json.dumps(extracted_data, ensure_ascii=False)
                                session.add(db_item); session.commit()
                            except: pass
                    else:
                        db_item = existing_item

                    processed_items_for_summary.append(db_item)

                    link_stmt = select(SearchItemLink).where(SearchItemLink.search_id == task_id, SearchItemLink.item_id == db_item.id)
                    if not session.exec(link_stmt).first():
                        session.add(SearchItemLink(search_id=task_id, item_id=db_item.id))
                        session.commit()
                except: continue

            # --- ФИНАЛ ---
            print(f"[DEBUG SERVICE] Generating summary...")
            summary_text = "Анализ завершен, но нейросеть не вернула текст."

            try:
                if processed_items_for_summary:
                    if is_deep_analysis:
                        # For deep analysis, we might want to use a different summarization approach
                        summary_text = await self.summarize_deep_analysis(search_request, processed_items_for_summary)
                    else:
                        summary_text = await summarize_search_results(search_request.query_text, processed_items_for_summary)
                else:
                    summary_text = "Товары не найдены или возникла ошибка при сборе."
            except Exception as e:
                summary_text = f"Ошибка генерации отчета: {str(e)}"

            # ВАЖНО: Если вдруг summary_text пустой, ставим заглушку, чтобы фронт не висел
            if not summary_text:
                summary_text = "Отчет готов (нет текста)."

            print(f"[DEBUG SERVICE] Final Summary: {summary_text[:50]}...")

            search_request.summary = summary_text
            search_request.status = "done"

            # If this is a deep analysis, update the stage
            if is_deep_analysis and search_request.mode == "deep":
                search_request.stage = "completed"

            session.add(search_request)
            session.commit()
            print(f"[DEBUG SERVICE] Task #{task_id} marked as DONE.")

    async def summarize_deep_analysis(self, search_request: SearchSession, items: list) -> str:
        """Generate a summary for deep analysis with SQL filtering"""
        if not items:
            return "Глубокий анализ: не найдено подходящих товаров."

        # For deep analysis, we might want to apply SQL filters based on interview data
        # This is a simplified version - in a real implementation, we would execute the SQL query
        # and return the filtered results

        # Prepare data for summary
        data_block = ""
        for i, item in enumerate(items[:10]):  # Show top 10 items
            specs = item.structured_data if item.structured_data else "Нет данных"
            data_block += f"ЛОТ #{i+1}\nНазвание: {item.title}\nЦена: {item.price}\nТТХ: {specs}\n\n"

        # If we have interview data, we could use it to customize the summary
        interview_criteria = "Не указаны"
        if search_request.interview_data:
            try:
                interview_data = json.loads(search_request.interview_data)
                # Extract criteria from interview data for the summary
                interview_criteria = str(list(interview_data.values())[-1]) if interview_data else "Не указаны"
            except:
                pass

        prompt = f"""Ты — аналитик цен Avito для глубокого исследования.
КРИТЕРИИ ПОЛЬЗОВАТЕЛЯ: "{interview_criteria}"
ДАННЫЕ РЫНКА:
{data_block}

ЗАДАЧА:
Напиши краткий аналитический отчет на русском языке для глубокого исследования.
Используй Markdown:
- **Жирный текст** для цен и ключевых названий.
- Списки для перечисления.

СТРУКТУРА:
1. **Обзор собранного** (сколько товаров проанализировано).
2. **Соответствие критериям** (какие лоты лучше всего соответствуют запросу).
3. **Рекомендации** (лучшие варианты с обоснованием).
4. **Риски** (потенциальные проблемы).

Будь краток, не пиши приветствий. Максимум 200-250 слов."""

        try:
            from llm_engine import client, MODEL_NAME
            import json

            response = await client.chat.completions.create(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1200
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Ошибка при создании отчета глубокого анализа: {e}"