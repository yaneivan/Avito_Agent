import json
import os
import base64
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:8080/v1")
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "not-needed")
MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "Qwen3-Vl-4B-Instruct")

client = AsyncOpenAI(base_url=LOCAL_LLM_URL, api_key=API_KEY)

def encode_image_to_base64(image_path: str) -> str | None:
    if not image_path or not os.path.exists(image_path): return None
    try:
        with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')
    except Exception as e:
        print(f"[ERROR] Image encode: {e}")
        return None

def clean_json(content: str) -> str:
    if "```json" in content: content = content.split("```json")[1].split("```")[0]
    elif "```" in content: content = content.split("```")[1].split("```")[0]
    return content.strip()

async def decide_action(history: list, available_schemas: list[str]) -> dict:
    print(f"\n[DEBUG LLM] Deciding action for: {history[-1]}")
    prompt = f"""Ты — помощник пользователя на сайте Avito.
Твоя задача: понять, хочет ли пользователь найти товар или просто болтает.

ПРАВИЛА:
1. Если пользователь пишет "привет", "как дела", "ты кто" — это action: "chat".
2. Если пользователь пишет "хочу купить", "найди", "нужен [товар]", "посоветуй" — это action: "search".
3. Не спрашивай про "объем закупки" или "тендеры". Это частная покупка 1 штуки.

ИСТОРИЯ: {history[-3:]}

ОТВЕТЬ ТОЛЬКО JSON:
{{
  "reasoning": "почему выбрано действие",
  "action": "search" или "chat",
  "search_query": "точный запрос для поиска (например 'MacBook Air M1') или null",
  "limit": 5,
  "schema_name": "general",
  "reply": "текст ответа"
}}"""
    try:
        res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.1)
        resp_text = clean_json(res.choices[0].message.content)
        print(f"[DEBUG LLM] Decision: {resp_text}")
        return json.loads(resp_text)
    except Exception as e:
        print(f"[ERROR LLM] Decide action: {e}")
        return {"action": "chat", "reply": "Я готов искать. Что вам нужно?", "reasoning": "error"}

async def conduct_interview(history: list, interview_data: str = "") -> dict:
    print(f"\n[DEBUG LLM] Interview step. Data: {interview_data}")
    prompt = f"""Ты — дружелюбный помощник на Авито. Помогаешь человеку купить вещь ДЛЯ СЕБЯ (1 шт).
НЕ спрашивай про: объем партии, условия поставки для юрлиц, сроки закупки.
ТВОЯ ЦЕЛЬ: Узнать только 2 вещи:
1. Что ищем (Категория/Товар).
2. Бюджет (Сколько денег).

Если пользователь уже назвал товар и цену (например "ноутбук за 30к") — НЕ задавай лишних вопросов, сразу завершай.

ТЕКУЩИЕ ДАННЫЕ: {interview_data}
ПОСЛЕДНЕЕ СООБЩЕНИЕ: {history[-1]}

ОТВЕТЬ ТОЛЬКО JSON:
{{
  "response": "твой вопрос или итог",
  "needs_more_info": true (если нет бюджета или товара) или false (если всё есть),
  "criteria_summary": "кратко: товар и бюджет (строка)",
  "reasoning": "почему"
}}"""
    try:
        res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.3)
        resp_text = clean_json(res.choices[0].message.content)
        print(f"[DEBUG LLM] Interview response: {resp_text}")
        return json.loads(resp_text)
    except Exception as e:
        print(f"[ERROR LLM] Interview: {e}")
        return {"response": "Что ищем и какой бюджет?", "needs_more_info": True, "criteria_summary": "", "reasoning": "error"}

async def deep_research_agent(history: list, current_state: dict) -> dict:
    """
    Универсальный агент для глубокого исследования
    current_state содержит информацию о текущем состоянии сессии
    """
    import json

    print(f"\n[DEBUG AGENT] Starting deep research agent")
    print(f"[DEBUG AGENT] Current state: {current_state}")
    print(f"[DEBUG AGENT] History length: {len(history)}, Last message: {history[-1] if history else 'None'}")

    tools = [
        {
            "type": "function",
            "function": {
                "name": "propose_schema",
                "description": "Предложить схему извлечения данных на основе критериев пользователя",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "criteria": {"type": "string", "description": "Критерии поиска"}
                    },
                    "required": ["criteria"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "proceed_to_search",
                "description": "Перейти к этапу поиска с указанной схемой",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "schema": {"type": "object", "description": "Схема извлечения данных"},
                        "search_query": {"type": "string", "description": "Поисковый запрос"}
                    },
                    "required": ["schema", "search_query"]
                }
            }
        }
    ]

    prompt = f"""
    Ты — агент глубокого исследования для поиска товаров на Авито.

    ТВОЯ ЗАДАЧА:
    1. Понять, что ищет пользователь (товар и бюджет)
    2. Если у тебя достаточно информации, предложи схему извлечения данных через инструмент propose_schema
    3. Если пользователь согласен с предложенной схемой, используй инструмент proceed_to_search
    4. Если пользователь не согласен с предложенной схемой или предлагает изменения,
       ответь ему напрямую, уточни требования и при необходимости снова предложи схему
    5. Если пользователь задает уточняющие вопросы, отвечай на них

    ТЕКУЩЕЕ СОСТОЯНИЕ: {current_state}
    ИСТОРИЯ ДИАЛОГА: {history[-10:]}

    Выбери подходящий инструмент или ответь пользователю напрямую.
    """

    try:
        print(f"[DEBUG AGENT] Sending request to LLM with tools")
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            tools=tools,
            tool_choice="auto",
            temperature=0.3
        )

        print(f"[DEBUG AGENT] LLM response received")
        print(f"[DEBUG AGENT] Finish reason: {response.choices[0].finish_reason}")
        print(f"[DEBUG AGENT] Message content: {response.choices[0].message.content}")

        # Проверяем, был ли вызван инструмент
        if response.choices[0].finish_reason == "tool_calls":
            print(f"[DEBUG AGENT] Tool calls detected")
            # Возвращаем информацию о вызове инструмента
            tool_calls = []
            for tool_call in response.choices[0].message.tool_calls:
                print(f"[DEBUG AGENT] Processing tool call: {tool_call.function.name}")
                # Выводим только краткую информацию об аргументах, без длинных значений
                import json
                try:
                    args_dict = json.loads(tool_call.function.arguments)
                    args_summary = {k: (f"<{type(v).__name__}>" if isinstance(v, (dict, list)) else v) for k, v in args_dict.items()}
                    print(f"[DEBUG AGENT] Tool arguments (summary): {args_summary}")
                except json.JSONDecodeError:
                    print(f"[DEBUG AGENT] Tool arguments: <could not parse>")

                tool_calls.append({
                    "name": tool_call.function.name,
                    "arguments": json.loads(tool_call.function.arguments)
                })

            result = {
                "type": "tool_call",
                "tool_calls": tool_calls,
                "message": response.choices[0].message.content or ""
            }

            # Выводим только краткую информацию о результатах
            tool_calls_summary = [{"name": tc["name"], "args_keys": list(tc["arguments"].keys())} for tc in result.get("tool_calls", [])]
            print(f"[DEBUG AGENT] Returning tool call result: {{'type': '{result['type']}', 'tool_calls_count': {len(result.get('tool_calls', []))}, 'tool_calls': {tool_calls_summary}}}")
            return result
        else:
            print(f"[DEBUG AGENT] Simple chat response detected")
            result = {
                "type": "chat",
                "message": response.choices[0].message.content,
                "tool_calls": []
            }

            print(f"[DEBUG AGENT] Returning chat result: {result}")
            return result
    except Exception as e:
        print(f"[ERROR LLM] Deep research agent: {e}")
        return {
            "type": "chat",
            "message": "Произошла ошибка при обработке запроса.",
            "tool_calls": []
        }


async def generate_schema_proposal(criteria: str) -> dict:
    print(f"[DEBUG LLM] Generating schema for: {criteria}")
    prompt = f"""Ты — аналитик данных. Твоя задача: создать исчерпывающую JSON-схему для извлечения характеристик товара: "{criteria}".

ТРЕБОВАНИЯ:
1. Создай от 8 до 15 полей, которые реально важны для выбора этого товара.
2. Включи технические характеристики (память, процессор, материал, размер).
3. Включи состояние (износ, дефекты, комплектность).
4. Для каждого поля укажи "type" (str, int, float, bool) и "desc" (описание на русском).

ПРИМЕР (для ноутбука):
{{
  "schema": {{
    "cpu": {{"type": "str", "desc": "Модель процессора"}},
    "ram_gb": {{"type": "int", "desc": "ОЗУ в ГБ"}},
    "storage_gb": {{"type": "int", "desc": "SSD/HDD в ГБ"}},
    "battery_cycles": {{"type": "int", "desc": "Циклы зарядки"}},
    "has_original_charger": {{"type": "bool", "desc": "Есть оригинальная зарядка"}}
  }},
  "reasoning": "Эти поля критичны для оценки б/у ноутбука"
}}

ОТВЕТЬ ТОЛЬКО JSON."""

    try:
        res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.2)
        return json.loads(clean_json(res.choices[0].message.content))
    except:
        return {"schema": {"title": {"type": "str", "desc": "Название"}}, "reasoning": "fallback"}

async def extract_product_features(title: str, desc: str, price: str, img_path: str, criteria: str, extraction_schema: dict = None) -> dict:
    """
    Анализирует товар и извлекает структурированные характеристики согласно утвержденной схеме.

    Args:
        title (str): Название товара
        desc (str): Описание товара
        price (str): Цена товара
        img_path (str): Путь к изображению товара
        criteria (str): Критерии поиска/запрос пользователя
        extraction_schema (dict, optional): Утвержденная схема извлечения данных.
                                          Если не указана, извлекаются общие характеристики.

    Returns:
        dict: Словарь с результатами, содержащий:
            - relevance_score (int): Оценка релевантности товара запросу
            - visual_notes (str): Комментарии по визуальному анализу
            - specs (dict): Извлеченные структурированные характеристики
    """
    from schemas import RelevanceEvaluation
    from pydantic import create_model
    import json

    # Если передана схема извлечения, создаем динамическую модель
    if extraction_schema:
        # Создаем динамические поля на основе схемы
        dynamic_fields = {}
        for field_name, field_info in extraction_schema.items():
            field_type = field_info.get("type", "str")
            # Преобразуем строковые типы в соответствующие Python-типы
            if field_type == "int":
                pydantic_type = (int, ...)
            elif field_type == "float":
                pydantic_type = (float, ...)
            elif field_type == "bool":
                pydantic_type = (bool, ...)
            else:  # по умолчанию str
                pydantic_type = (str, ...)

            dynamic_fields[field_name] = pydantic_type

        # Создаем динамическую модель, наследуясь от RelevanceEvaluation
        DynamicEvaluation = create_model(
            'DynamicEvaluation',
            relevance_score=(int, ...),
            visual_notes=(str, ...),
            specs=(dict, ...),
            **dynamic_fields
        )

        # Формируем промпт с учетом схемы
        schema_info = f"Требуется извлечь следующие характеристики: {list(extraction_schema.keys())}. "
        schema_description = json.dumps(DynamicEvaluation.model_json_schema(), ensure_ascii=False, indent=2)
        prompt = f"""Оцени товар: "{title}", цена: {price}. Запрос: "{criteria}".
{schema_info}Ты должен вернуть JSON-объект, строго соответствующий следующей схеме:
{schema_description}"""
    else:
        # Если схема не передана, используем базовую модель
        schema_info = ""
        schema_description = json.dumps(RelevanceEvaluation.model_json_schema(), ensure_ascii=False, indent=2)
        prompt = f"""Оцени товар: "{title}", цена: {price}. Запрос: "{criteria}".
{schema_info}Ты должен вернуть JSON-объект, строго соответствующий следующей схеме:
{schema_description}"""
        DynamicEvaluation = RelevanceEvaluation

    msg = [{"type": "text", "text": prompt}]
    b64 = encode_image_to_base64(img_path)
    if b64: msg.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    try:
        # Используем Structured Outputs для гарантии корректной структуры ответа
        completion = await client.beta.chat.completions.parse(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": msg}],
            response_format=DynamicEvaluation,  # Передаем динамическую модель
            temperature=0.1
        )

        # Возвращаем результат как словарь
        result = completion.choices[0].message.parsed.dict()

        # Если использовалась динамическая модель, перемещаем извлеченные поля в specs
        if extraction_schema and DynamicEvaluation != RelevanceEvaluation:
            extracted_values = {}
            for field_name in extraction_schema.keys():
                if field_name in result:
                    extracted_values[field_name] = result[field_name]
                    # Удаляем поле из результата, чтобы не дублировать
                    del result[field_name]

            # Обновляем поле specs с извлеченными значениями
            result["specs"] = extracted_values

        return result
    except Exception as e:
        print(f"[ERROR LLM] Extract product features: {e}")
        # Возвращаем валидный ответ по умолчанию
        default_response = RelevanceEvaluation(relevance_score=1, visual_notes="Ошибка анализа", specs={})
        return default_response.dict()

async def rank_items_group(items_data: list, criteria: str) -> dict:
    print(f"[DEBUG LLM] Ranking group of {len(items_data)}")
    prompt = f"Сравни 5 товаров: {items_data} для '{criteria}'. JSON: {{ 'ranks': [{{'item_id':id, 'score':1-5}}] }}"
    res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.2)
    return json.loads(clean_json(res.choices[0].message.content))

async def summarize_search_results(query: str, items: list) -> dict:
    print(f"[DEBUG LLM] Summarizing {len(items)} items")
    data = "\n".join([f"- {i.title} ({i.price}): {i.visual_notes}" for i in items[:10]])
    prompt = f"Напиши отчет в Markdown по запросу '{query}'. Товары:\n{data}\nJSON: {{ 'summary': 'текст', 'reasoning': '' }}"
    try:
        res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.4)
        return json.loads(clean_json(res.choices[0].message.content))
    except Exception as e:
        print(f"[ERROR LLM] Summary: {e}")
        return {"summary": "Отчет не создан из-за ошибки.", "reasoning": str(e)}

async def generate_schema_structure(topic: str) -> dict:
    return {"schema": {"title": {"type": "str", "desc": "Название"}, "price": {"type": "int", "desc": "Цена"}}}