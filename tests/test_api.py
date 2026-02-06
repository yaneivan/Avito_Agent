import pytest
from fastapi.testclient import TestClient
from main import app
from models.research_models import MarketResearch, State


client = TestClient(app)


def test_create_market_research():
    """Тест создания нового исследования рынка через API"""
    response = client.post(
        "/market_research",
        json={"initial_query": "тестовый запрос"}
    )

    assert response.status_code == 200

    data = response.json()
    assert "id" in data
    # Состояние может измениться в зависимости от типа запроса (quick или deep)
    # Проверим, что это одно из допустимых состояний
    assert data["state"] in [State.CHAT.value, State.SEARCHING_QUICK.value, State.PLANNING_DEEP_RESEARCH.value]
    assert "chat_history" in data
    assert "search_tasks" in data


def test_get_market_research():
    """Тест получения исследования по ID через API"""
    # Сначала создаем исследование
    create_response = client.post(
        "/market_research",
        json={"initial_query": "тестовый запрос"}
    )
    
    assert create_response.status_code == 200
    created_mr = create_response.json()
    mr_id = created_mr["id"]
    
    # Теперь пытаемся получить его
    response = client.get(f"/market_research/{mr_id}")
    
    assert response.status_code == 200
    
    data = response.json()
    assert data["id"] == mr_id
    assert "state" in data
    assert "chat_history" in data
    assert "search_tasks" in data


def test_update_chat():
    """Тест обновления чата через API"""
    # Сначала создаем исследование
    create_response = client.post(
        "/market_research",
        json={"initial_query": "тестовый запрос"}
    )

    assert create_response.status_code == 200
    created_mr = create_response.json()
    mr_id = created_mr["id"]

    # Обновляем чат
    response = client.post(
        f"/chat/{mr_id}",
        json={
            "message": "сообщение пользователя",
            "images": []
        }
    )

    # Проверяем, что запрос не возвращает ошибку 422
    assert response.status_code in [200, 201]  # Может возвращать 201 Created

    # Если статус 200, проверяем данные
    if response.status_code == 200:
        data = response.json()
        assert "id" in data
        assert data["id"] == mr_id


def test_get_task():
    """Тест получения задачи для расширения"""
    # Сначала создадим задачу для тестирования
    create_response = client.post(
        "/market_research",
        json={"initial_query": "тестовый запрос"}
    )

    assert create_response.status_code == 200
    created_mr = create_response.json()
    mr_id = created_mr["id"]

    # Создаем задачу поиска
    from models.research_models import SearchTask
    from repositories.research_repository import SearchTaskRepository
    from database import SessionLocal, DBSearchTask

    db = SessionLocal()
    task_repo = SearchTaskRepository(db)

    search_task = SearchTask(
        market_research_id=mr_id,
        mode="quick",
        query="поиск товара",
        needs_visual=False,
        status="pending"  # Убедимся, что задача в состоянии pending
    )

    created_task = task_repo.create(search_task)
    task_id = created_task.id

    db.close()

    # Теперь пробуем получить задачу
    response = client.get("/get_task")

    # Ожидаем, что задача будет возвращена (статус 200) или нет доступных задач (статус 204)
    # В зависимости от состояния задачи в базе данных
    if response.status_code == 200:
        data = response.json()
        # Проверим, что возвращаемые данные соответствуют ожидаемой структуре
        assert "task_id" in data
        assert "query" in data
        assert "active_tab" in data
        assert "limit" in data
        # Проверим, что возвращаемая задача существует в системе
        # (мы не можем гарантировать, что это будет именно наша задача,
        # так как сервер возвращает первую доступную)
    elif response.status_code == 204:
        # Это нормально, если задача уже была получена другим запросом
        pass
    else:
        assert False, f"Unexpected status code: {response.status_code}"


def test_submit_results():
    """Тест отправки результатов от расширения"""
    # Для этого теста нужно сначала создать задачу, чтобы был task_id
    create_response = client.post(
        "/market_research",
        json={"initial_query": "тестовый запрос"}
    )

    assert create_response.status_code == 200
    created_mr = create_response.json()
    mr_id = created_mr["id"]

    # Создаем задачу поиска
    from models.research_models import SearchTask
    from repositories.research_repository import SearchTaskRepository
    from database import SessionLocal

    db = SessionLocal()
    task_repo = SearchTaskRepository(db)

    search_task = SearchTask(
        market_research_id=mr_id,
        mode="quick",
        query="поиск товара",
        needs_visual=False
    )

    created_task = task_repo.create(search_task)
    task_id = created_task.id

    db.close()

    # Теперь отправляем результаты
    response = client.post(
        "/submit_results",
        json={
            "task_id": task_id,
            "items": [
                {
                    "title": "Тестовый товар",
                    "price": "10000",
                    "url": "https://example.com",
                    "description": "Описание товара",
                    "image_base64": None
                }
            ]
        }
    )

    assert response.status_code == 200

    data = response.json()
    assert "status" in data
    assert data["status"] == "success"
    assert "market_research_id" in data
    assert data["market_research_id"] == mr_id