from typing import List, Dict
from utils.llm_client import get_completion, parse_tool_calls
from utils.logger import logger


def get_available_tools():
    """
    Возвращает список доступных инструментов для LLM
    """
    tools = [
        {
            "name": "quick_research",
            "description": "Быстрый поиск товаров на Avito по заданному запросу",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос для поиска товаров"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество товаров для возврата"
                    }
                },
                "required": ["query", "limit"]
            }
        },
        {
            "name": "deep_research",
            "description": "Глубокий анализ товаров с использованием схемы структурирования",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Поисковый запрос для поиска товаров"
                    },
                    "schema_id": {
                        "type": "integer",
                        "description": "ID схемы для структурирования данных"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Максимальное количество товаров для возврата"
                    }
                },
                "required": ["query", "schema_id", "limit"]
            }
        }
    ]
    return tools


def process_llm_response_with_tools(messages: List[Dict]):
    """
    Обработка ответа LLM с возможностью вызова инструментов
    """
    logger.info("Обрабатываем ответ LLM с возможными вызовами инструментов")
    
    # Получаем ответ от LLM
    response = get_completion(messages, tools=get_available_tools())
    
    # Проверяем, есть ли вызовы инструментов в ответе
    if hasattr(response, 'tool_calls') and response.tool_calls:
        logger.info(f"Найдено {len(response.tool_calls)} вызовов инструментов")
        
        # Обрабатываем каждый вызов инструмента
        for tool_call in response.tool_calls:
            function_name = tool_call.function.name
            arguments = tool_call.function.arguments
            
            logger.info(f"Вызываем инструмент {function_name} с аргументами: {arguments}")
            
            # В зависимости от имени инструмента, вызываем соответствующую функцию
            if function_name == "quick_research":
                # Выполняем быстрый поиск
                result = quick_research_tool(arguments)
            elif function_name == "deep_research":
                # Выполняем глубокий поиск
                result = deep_research_tool(arguments)
            else:
                logger.warning(f"Неизвестный инструмент: {function_name}")
                result = {"error": f"Unknown tool: {function_name}"}
            
            # Добавляем результат вызова инструмента обратно в сообщения
            messages.append({
                "role": "tool",
                "content": str(result),
                "tool_call_id": tool_call.id
            })
        
        # После выполнения инструментов, снова обращаемся к LLM с результатами
        final_response = get_completion(messages)
        return final_response
    else:
        # Если нет вызовов инструментов, возвращаем обычный ответ
        logger.info("Ответ LLM не содержит вызовов инструментов")
        return response


def quick_research_tool(arguments: str) -> Dict:
    """
    Инструмент для быстрого поиска товаров
    """
    import json
    args = json.loads(arguments)
    query = args.get("query", "")
    limit = args.get("limit", 10)
    
    logger.info(f"Выполняем быстрый поиск по запросу: '{query}', лимит: {limit}")
    
    # В реальной реализации здесь будет вызов к браузерному расширению
    # или к базе данных для получения результатов
    # Пока возвращаем заглушку
    
    return {
        "status": "success",
        "query": query,
        "limit": limit,
        "results_count": min(limit, 5),  # Возвращаем максимум 5 результатов как пример
        "results": [
            {"title": "Товар 1", "price": "10000", "url": "https://example.com/1"},
            {"title": "Товар 2", "price": "15000", "url": "https://example.com/2"},
            {"title": "Товар 3", "price": "12000", "url": "https://example.com/3"},
            {"title": "Товар 4", "price": "18000", "url": "https://example.com/4"},
            {"title": "Товар 5", "price": "20000", "url": "https://example.com/5"}
        ]
    }


def deep_research_tool(arguments: str) -> Dict:
    """
    Инструмент для глубокого анализа товаров
    """
    import json
    args = json.loads(arguments)
    query = args.get("query", "")
    schema_id = args.get("schema_id", 0)
    limit = args.get("limit", 10)
    
    logger.info(f"Выполняем глубокий поиск по запросу: '{query}', schema_id: {schema_id}, лимит: {limit}")
    
    # В реальной реализации здесь будет вызов к браузерному расширению
    # или к базе данных для получения результатов с последующим 
    # структурированием по схеме
    # Пока возвращаем заглушку
    
    return {
        "status": "success",
        "query": query,
        "schema_id": schema_id,
        "limit": limit,
        "results_count": min(limit, 3),  # Возвращаем максимум 3 результата как пример
        "results": [
            {
                "title": "Товар 1",
                "price": "10000",
                "url": "https://example.com/1",
                "structured_data": {
                    "feature1": "значение1",
                    "feature2": "значение2"
                }
            },
            {
                "title": "Товар 2", 
                "price": "15000",
                "url": "https://example.com/2",
                "structured_data": {
                    "feature1": "значение3",
                    "feature2": "значение4"
                }
            },
            {
                "title": "Товар 3",
                "price": "12000", 
                "url": "https://example.com/3",
                "structured_data": {
                    "feature1": "значение5",
                    "feature2": "значение6"
                }
            }
        ]
    }