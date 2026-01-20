import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch
from llm_engine import decide_action

# Правильный мок для OpenAI
def mock_openai_response(content):
    # Сам объект ответа - обычный MagicMock (не async)
    mock_resp = MagicMock()
    # Внутренняя структура
    mock_choice = MagicMock()
    mock_choice.message.content = content
    mock_resp.choices = [mock_choice]
    return mock_resp

@pytest.mark.asyncio
async def test_decide_action_clean_json():
    fake_json = '{"action": "search", "search_query": "test", "limit": 5, "schema_name": "General"}'
    
    # Patch возвращает AsyncMock, который при await вернет наш mock_resp
    with patch("llm_engine.client.chat.completions.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_openai_response(fake_json)
        
        result = await decide_action([], [])
        assert result["action"] == "search"
        assert result["search_query"] == "test"

@pytest.mark.asyncio
async def test_decide_action_markdown_json():
    fake_markdown = 'Here is the json:\n```json\n{"action": "chat", "reply": "Hello"}\n```'
    
    with patch("llm_engine.client.chat.completions.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_openai_response(fake_markdown)
        
        result = await decide_action([], [])
        assert result["action"] == "chat"
        assert result["reply"] == "Hello"

@pytest.mark.asyncio
async def test_decide_action_broken_json():
    fake_broken = '{action: "search" ... invalid' # Невалидный JSON
    
    with patch("llm_engine.client.chat.completions.create", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = mock_openai_response(fake_broken)
        
        result = await decide_action([], [])
        # Проверяем, что сработал except и вернулся фоллбэк
        assert result["action"] == "chat"
        assert "Ошибка" in result.get("reasoning", "")