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
    with open(image_path, "rb") as f: return base64.b64encode(f.read()).decode('utf-8')

def clean_json(content: str) -> str:
    if "```json" in content: content = content.split("```json")[1].split("```")[0]
    elif "```" in content: content = content.split("```")[1].split("```")[0]
    return content.strip()

async def decide_action(history: list) -> dict:
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
    res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.1)
    resp_text = clean_json(res.choices[0].message.content)
    print(f"[DEBUG LLM] Decision: {resp_text}")
    return json.loads(resp_text)

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
    Ты — профессиональный консультант по покупкам на Avito. Твоя цель — провести интервью, чтобы сформировать идеальный запрос для парсинга и анализа рынка.

    ЛОГИКА ТВОЕЙ РАБОТЫ:
    1. ЭТАП ЗНАКОМСТВА: Если пользователь просто здоровается или пишет не по делу — поддержи диалог и мягко спроси, какой товар его интересует и какой у него бюджет.
    2. ЭТАП ИНТЕРВЬЮ: Ты должен узнать (1) КАТЕГОРИЮ товара и (2) БЮДЖЕТ. Пока эти два пункта не ясны, ты только задаешь вопросы в текстовом виде. Инструменты не вызываешь.
    3. ЭТАП ПРЕДЛОЖЕНИЯ (propose_schema): Только когда известны и товар, и бюджет, ты предлагаешь JSON-схему полей, которые нужно извлечь (например: пробег, память, состояние).
    4. ЭТАП ПОДТВЕРЖДЕНИЯ (proceed_to_search): Если пользователь подтвердил предложенную схему (сказал "да", "ок", "поехали"), вызывай инструмент перехода к поиску.

    ТЕКУЩЕЕ СОСТОЯНИЕ СИСТЕМЫ: {current_state}
    ИСТОРИЯ ДИАЛОГА (последние сообщения): {history[-10:]}

    КРИТИЧЕСКИЕ ПРАВИЛА:
    - ЗАПРЕЩЕНО вызывать `propose_schema` на приветствие ("привет", "хай") или пустой разговор.
    - Сначала всегда отвечай текстом, чтобы уточнить детали, если информации мало.
    - Если пользователь хочет изменить схему — вернись на этап интервью.
    - Твой ответ должен быть либо вызовом инструмента, либо обычным текстом, но НЕ ОБОИМ СРАЗУ.

    Действуй:
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
        res = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            response_format={"type": "json_object"}  # Указываем, что ожидаем JSON-объект
        )
        return json.loads(res.choices[0].message.content)
    except Exception as e:
        print(f"[ERROR LLM] Failed to generate schema: {e}")
        raise ValueError(f"Не удалось сгенерировать схему извлечения данных для запроса '{criteria}'. Пожалуйста, уточните запрос или повторите попытку.")

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
    import json

    # Если передана схема извлечения, извлекаем характеристики по схеме
    if extraction_schema:
        # Проверяем, что extraction_schema - это словарь
        if isinstance(extraction_schema, str):
            try:
                extraction_schema = json.loads(extraction_schema)
            except json.JSONDecodeError:
                print(f"[ERROR LLM] Failed to decode extraction schema: {extraction_schema}")
                extraction_schema = {}

        # Формируем промпт для извлечения характеристик по схеме
        schema_info = f"Требуется извлечь следующие характеристики: {list(extraction_schema.keys())}. "
        extraction_prompt = f"""Проанализируй товар "{title}" и извлеки следующие характеристики в соответствии с запросом "{criteria}":
{schema_info}
Описание: {desc}
Цена: {price}

Верни JSON-объект с извлеченными значениями для каждой характеристики.
Если характеристика не указана в описании или на изображении, НЕ ВКЛЮЧАЙ ЕЁ в результат."""

        extraction_msg = [{"type": "text", "text": extraction_prompt}]
        b64 = encode_image_to_base64(img_path)
        if b64:
            extraction_msg.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

        # Извлекаем структурированные данные по схеме
        extraction_completion = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": extraction_msg}],
            temperature=0.1
        )

        # Извлекаем JSON из ответа
        content = extraction_completion.choices[0].message.content
        # Убираем маркеры кода, если они есть
        if content.startswith('```json'):
            content = content[7:content.rfind('```')]
        elif content.startswith('```'):
            content = content[3:content.rfind('```')]

        extracted_specs = json.loads(content.strip())

        # Валидируем и конвертируем извлеченные данные в соответствии со схемой
        validated_specs = {}
        for field_name, field_info in extraction_schema.items():
            if field_name in extracted_specs:
                expected_type = field_info.get("type", "str")
                value = extracted_specs[field_name]

                # Конвертируем значение к ожидаемому типу
                if value is not None and value != "null":
                    if expected_type == "int":
                        validated_specs[field_name] = int(value)
                    elif expected_type == "float":
                        validated_specs[field_name] = float(value)
                    elif expected_type == "bool":
                        validated_specs[field_name] = bool(value)
                    else:  # строковый тип
                        validated_specs[field_name] = str(value)
                    # Если значение null или не удалось конвертировать, не включаем в результат
    else:
        validated_specs = {}

    # Теперь получаем оценку релевантности
    relevance_prompt = f"""Оцени, насколько товар "{title}" (цена: {price}) соответствует запросу "{criteria}".
Оцени релевантность по шкале от 0 до 100, где 0 - совсем не подходит, 100 - идеально подходит.
Верни только JSON-объект с полями relevance_score (число) и visual_notes (строка с комментарием)."""

    relevance_msg = [{"type": "text", "text": relevance_prompt}]
    b64 = encode_image_to_base64(img_path)
    if b64:
        relevance_msg.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

    relevance_completion = await client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": relevance_msg}],
        temperature=0.1
    )

    content = relevance_completion.choices[0].message.content
    if content.startswith('```json'):
        content = content[7:content.rfind('```')]
    elif content.startswith('```'):
        content = content[3:content.rfind('```')]

    relevance_result = json.loads(content.strip())

    # Собираем финальный результат
    result = {
        "relevance_score": relevance_result.get("relevance_score", 1),
        "visual_notes": relevance_result.get("visual_notes", "Ошибка анализа"),
        "specs": validated_specs
    }

    return result

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
    # Эта функция используется в chat.py для генерации структуры схемы
    # topic не используется в текущей реализации, но сохранен для совместимости
    return {"schema": {"title": {"type": "str", "desc": "Название"}, "price": {"type": "int", "desc": "Цена"}}}