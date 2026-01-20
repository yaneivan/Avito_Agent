import pytest
from unittest.mock import patch
from sqlmodel import select  # <--- ИМПОРТ ВЫНЕСЕН СЮДА
from services import ProcessingService
from database import SearchSession, Item, ExtractionSchema
from pydantic import BaseModel

class MockItem(BaseModel):
    title: str = "Test Item"
    price: str = "100"
    url: str = "http://test.com/1"
    description: str = "Desc"
    local_path: str = None
    image_base64: str = None

@pytest.mark.asyncio
async def test_process_incoming_data(session):
    """
    Тестируем полный цикл: Данные пришли -> Сохранились -> Статус Done -> Саммари записано
    """
    # 1. Сначала создаем СХЕМУ
    schema = ExtractionSchema(
        name="TestSchema", 
        description="Test desc", 
        structure_json='{"field": {"type": "str", "desc": "test"}}'
    )
    session.add(schema)
    session.commit()
    session.refresh(schema)

    # 2. Создаем задачу, привязанную к этой схеме
    task = SearchSession(
        query_text="test", 
        status="processing", 
        schema_id=schema.id
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    task_id = task.id

    # 3. Запускаем тест с моками
    with patch("services.engine", session.bind):
        service = ProcessingService()
        
        # Мокаем методы LLM, чтобы они возвращали фейковые данные
        with patch("services.extract_specs", return_value={"test": "data"}) as mock_extract, \
             patch("services.summarize_search_results", return_value="FINAL SUMMARY OK") as mock_summ:
            
            items = [MockItem(url="http://test.com/1"), MockItem(url="http://test.com/2")]
            
            await service.process_incoming_data(task_id, items)

            # Проверяем, что экстракция вызывалась
            assert mock_extract.called, "LLM Extraction was not called!"

    # 4. Проверяем результаты в БД
    session.refresh(task)
    
    assert task.status == "done"
    assert task.summary == "FINAL SUMMARY OK"
    
    # Теперь select доступен, так как импортирован в начале файла
    items_in_db = session.exec(select(Item)).all()

    assert len(items_in_db) == 2
    # Проверяем, что JSON записался (двойные кавычки, так как json.dumps)
    # Внимание: сравнение строк JSON может быть чувствительно к пробелам
    # Лучше распарсить обратно или проверить вхождение
    assert '{"test": "data"}' in items_in_db[0].structured_data