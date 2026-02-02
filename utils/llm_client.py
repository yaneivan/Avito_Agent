from openai import OpenAI
from config import LOCAL_LLM_URL, LOCAL_LLM_API_KEY, LOCAL_LLM_MODEL
from pydantic import BaseModel
from typing import List, Dict, Any, Union
import json
from utils.logger import logger

client = OpenAI(base_url=LOCAL_LLM_URL, api_key=LOCAL_LLM_API_KEY)

def get_completion(
    messages: List[Dict],
    response_format: Any = None,
    tools: List[Dict] = None,
    tool_choice: Union[str, Dict] = None
):
    """
    Получение ответа от LLM
    :param messages: список сообщений для модели
    :param response_format: Pydantic модель для структурированного вывода
    :param tools: список инструментов для вызова
    :param tool_choice: выбор инструмента ('auto', 'required', 'none' или конкретный инструмент)
    :return: ответ модели
    """
    logger.info(f"Отправляем запрос к LLM с {len(messages)} сообщениями")

    try:
        # Подготовим параметры для вызова
        params = {
            "model": LOCAL_LLM_MODEL,
            "messages": messages
        }

        if response_format:
            # Используем структурированный вывод
            params["response_format"] = response_format
            completion = client.beta.chat.completions.parse(**params)
        else:
            # Добавим параметры для инструментов, если они указаны
            if tools:
                params["tools"] = tools
                if tool_choice:
                    params["tool_choice"] = tool_choice

            completion = client.chat.completions.create(**params)

        response = completion.choices[0].message

        # Логируем информацию о токенах, если она доступна
        if hasattr(completion, 'usage'):
            logger.info(f"Токены: prompt={completion.usage.prompt_tokens}, "
                       f"completion={completion.usage.completion_tokens}, "
                       f"total={completion.usage.total_tokens}")

        logger.info("Успешно получен ответ от LLM")
        logger.info(f"Ответ от LLM: {response.content if hasattr(response, 'content') else 'No content'}")

        return response
    except Exception as e:
        logger.error(f"Ошибка при обращении к LLM: {e}")
        raise


def parse_tool_calls(tool_calls_str: str) -> List[Dict]:
    """
    Парсинг вызовов инструментов из текстового формата
    :param tool_calls_str: строка с вызовами инструментов в формате JSON
    :return: список вызовов инструментов
    """
    logger.info("Парсим вызовы инструментов")
    logger.info(f"Строка вызовов инструментов: {tool_calls_str}")

    try:
        # Удаляем лишние символы, если они есть
        cleaned_str = tool_calls_str.strip()

        # Если строка начинается с ```json и заканчивается ```, извлекаем JSON
        if cleaned_str.startswith("```json"):
            cleaned_str = cleaned_str[7:]  # Удаляем "```json"
        if cleaned_str.endswith("```"):
            cleaned_str = cleaned_str[:-3]  # Удаляем "```"

        # Парсим JSON
        tool_calls = json.loads(cleaned_str)

        # Если результат - один вызов инструмента, оборачиваем в список
        if isinstance(tool_calls, dict) and "name" in tool_calls:
            tool_calls = [tool_calls]

        logger.info(f"Успешно распаршено {len(tool_calls)} вызовов инструментов")
        logger.info(f"Вызовы инструментов: {tool_calls}")
        return tool_calls
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка при парсинге вызовов инструментов: {e}")
        raise
    except Exception as e:
        logger.error(f"Неизвестная ошибка при парсинге вызовов инструментов: {e}")
        raise