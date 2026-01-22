import json
import os
import base64
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Настройки для локального Docker (llama.cpp server)
LOCAL_LLM_URL = os.getenv("LOCAL_LLM_URL", "http://localhost:8080/v1")
API_KEY = os.getenv("LOCAL_LLM_API_KEY", "not-needed")
MODEL_NAME = os.getenv("LOCAL_LLM_MODEL", "Qwen3-Vl-4B-Instruct")

client = AsyncOpenAI(
    base_url=LOCAL_LLM_URL,
    api_key=API_KEY,
)

def encode_image_to_base64(image_path: str) -> str | None:
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Image encode error: {e}")
        return None

async def decide_action(history: list, available_schemas: list[str]) -> dict:
    schemas_str = ", ".join(available_schemas)
    context_str = ""
    for msg in history[-5:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg.get("content", "")
        context_str += f"{role}: {content}\n"

    prompt = f"""Ты — мозг ассистента Avito.
Твоя задача: понять, нужен ли пользователю поиск товаров или просто ответ в чате.

ДОСТУПНЫЕ СХЕМЫ: [{schemas_str}]
ИСТОРИЯ:
{context_str}

ИНСТРУКЦИЯ:
- Будь гибким. Если в сообщении есть намерение найти/сравнить/купить — выбирай "search".
- Если это просто разговор, вопрос о тебе или уточнение без поиска — выбирай "chat".
- В поле "reasoning" кратко напиши ход своих мыслей.
- В поле "internal_thoughts" укажи внутренние размышления, почему ты принял то или иное решение.
- В поле "next_action" укажи следующее действие: "continue_chat", "start_search", "start_deep_research", "provide_recommendations".
- Если action: "chat", то search_query, limit и schema_name ДОЛЖНЫ БЫТЬ null.
- Если создаешь новую схему, дай ей короткое имя на английском.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "reasoning": "почему выбрано это действие",
    "internal_thoughts": "внутренние размышления о принятии решения",
    "next_action": "continue_chat | start_search | start_deep_research | provide_recommendations",
    "action": "search" | "chat",
    "search_query": "ключевые слова для поиска или null",
    "limit": 5,
    "schema_name": "имя_схемы или null",
    "reply": "текст твоего ответа если action=chat или null"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=600
        )
        content = response.choices[0].message.content
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except:
        return {
            "action": "chat",
            "reply": "Нейросеть временно недоступна. Пожалуйста, повторите попытку позже.",
            "reasoning": "Ошибка подключения к LLM",
            "internal_thoughts": "Произошла ошибка при подключении к LLM",
            "next_action": "continue_chat",
            "search_query": None,
            "limit": 5,
            "schema_name": None
        }

async def extract_specs(title: str, desc: str, price: str, img_path: str | None) -> dict:
    prompt = f"""Извлеки характеристики из объявления Avito.
Заголовок: {title}
Цена: {price}
Описание: {desc[:1000]}

ИНСТРУКЦИЯ:
- Найди бренд, модель и ключевые технические параметры.
- В поле "notes" напиши важные пометки (например: 'продажа только оптом', 'несколько штук в наличии', 'есть дефекты').
- В поле "reasoning" кратко напиши ход своих мыслей.
- В поле "internal_thoughts" укажи внутренние размышления, почему ты принял то или иное решение.
- Верни ТОЛЬКО JSON.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "specs": "извлеченные характеристики",
    "reasoning": "почему выбрано это действие",
    "internal_thoughts": "внутренние размышления о принятии решения"
}}"""

    messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]

    if img_path:
        b64_img = encode_image_to_base64(img_path)
        if b64_img:
            messages[0]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}
            })

    try:
        print(f"LOG: Extracting specs for {title}...")
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            max_tokens=1000,
            temperature=0.0
        )
        res = response.choices[0].message.content
        if "```" in res:
            res = res.split("```")[1].replace("json", "").strip()
        parsed_res = json.loads(res)
        return parsed_res["specs"]
    except Exception as e:
        print(f"LOG ERROR Extraction: {e}")
        return {"notes": "Ошибка извлечения данных"}

async def generate_schema_structure(topic: str) -> dict:
    prompt = f"""Создай простую JSON схему (5-6 полей) для извлечения данных о товарах типа '{topic}'.
Используй только типы "str", "int", "float".
Каждое поле должно иметь "type" и "desc".
В поле "reasoning" кратко напиши ход своих мыслей.
- В поле "internal_thoughts" укажи внутренние размышления, почему ты принял то или иное решение.
- В поле "next_action" укажи следующее действие: "return_schema", "request_more_info", "modify_schema".
Верни ТОЛЬКО JSON.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "schema": "схема в формате JSON",
    "reasoning": "почему выбрано это действие",
    "internal_thoughts": "внутренние размышления о принятии решения",
    "next_action": "return_schema | request_more_info | modify_schema"
}}"""
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=600
        )
        res = response.choices[0].message.content
        if "```" in res:
            res = res.split("```")[1].replace("json", "").strip()
        parsed_res = json.loads(res)
        json.loads(parsed_res["schema"]) # Валидация
        return parsed_res
    except:
        default_schema = json.dumps({
            "brand": {"type": "str", "desc": "Бренд"},
            "model": {"type": "str", "desc": "Модель"},
            "condition": {"type": "str", "desc": "Состояние"}
        })
        return {
            "schema": default_schema,
            "reasoning": "Ошибка генерации схемы",
            "internal_thoughts": "Произошла ошибка при генерации схемы, возвращаю стандартную схему",
            "next_action": "return_schema"
        }

async def summarize_search_results(query: str, items: list) -> dict:
    if not items:
        return {
            "summary": "Поиск не дал результатов.",
            "reasoning": "Нет данных для анализа",
            "internal_thoughts": "Нет результатов поиска для создания отчета",
            "next_action": "inform_no_results"
        }

    data_block = ""
    for i, item in enumerate(items[:10]):
        specs = item.structured_data if item.structured_data else "Нет данных"
        data_block += f"ЛОТ #{i+1}\nНазвание: {item.title}\nЦена: {item.price}\nТТХ: {specs}\n\n"

    prompt = f"""Ты — аналитик цен Avito.
ЗАПРОС ПОЛЬЗОВАТЕЛЯ: "{query}"
ДАННЫЕ РЫНКА:
{data_block}

ЗАДАЧА:
Напиши краткий аналитический отчет на русском языке.
Используй Markdown:
- **Жирный текст** для цен и ключевых названий.
- Списки для перечисления.

СТРУКТУРА:
1. **Диапазон цен** (от и до).
2. **Лучший выбор** (укажи номер лота и почему это выгодно).
3. **Риски** (подозрительно дешево, неполное описание).

Будь краток, не пиши приветствий. Максимум 150-200 слов.

ИНСТРУКЦИЯ:
- В поле "reasoning" кратко напиши ход своих мыслей.
- В поле "internal_thoughts" укажи внутренние размышления, почему ты принял то или иное решение.
- В поле "next_action" укажи следующее действие: "present_results", "request_feedback", "suggest_alternatives".

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "summary": "аналитический отчет",
    "reasoning": "почему выбрано это действие",
    "internal_thoughts": "внутренние размышления о принятии решения",
    "next_action": "present_results | request_feedback | suggest_alternatives"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1200
        )
        content = response.choices[0].message.content
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        return {
            "summary": f"Ошибка при создании отчета: {e}",
            "reasoning": "Ошибка при создании отчета",
            "internal_thoughts": f"Произошла ошибка при создании отчета: {e}",
            "next_action": "inform_error"
        }

async def plan_search_action(user_text: str) -> dict:
    """Для обратной совместимости с вызовами в server.py"""
    return await decide_action([{"role": "user", "content": user_text}], [])

async def conduct_interview(history: list) -> dict:
    """Conduct an interview to gather user requirements for deep research"""
    context_str = ""
    for msg in history[-5:]:  # Take last 5 messages
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg.get("content", "")
        context_str += f"{role}: {content}\n"

    prompt = f"""Ты — агент для глубокого анализа рынка. Твоя задача — собрать минимально необходимую информацию для поиска товаров и принять решение о переходе к следующему этапу.

ИСТОРИЯ:
{context_str}

КРИТЕРИИ ЗАВЕРШЕНИЯ ИНТЕРВЬЮ:
- Узнай бюджет (минимум диапазон или сумма)
- Узнай целевую категорию товара (ноутбук, смартфон и т.д.)

ИНСТРУКЦИЯ:
- Если в истории уже есть информация, удовлетворяющая критериям завершения, НЕ задавай повторные вопросы.
- Если вся необходимая информация собрана, сообщи пользователю об этом и предложи перейти к следующему этапу.
- Если информации недостаточно, задавай конкретные уточняющие вопросы.
- Если пользователь дал базовую информацию (категория и бюджет), но не хочет уточнять детали, НЕ настаивай - переходи к следующему этапу.
- В поле "reasoning" кратко опиши, вся ли необходимая информация собрана.
- В поле "internal_thoughts" укажи, какие данные уже собраны и чего не хватает.
- В поле "next_action" укажи: "continue_interview" если нужно больше информации, "propose_schema" если вся информация собрана.
- Устанавливай "needs_more_info" в false, если вся необходимая информация собрана.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "response": "текст ответа пользователю - краткое резюме собранных данных и предложение перейти к следующему этапу, если вся информация собрана, или уточняющий вопрос, если информации недостаточно. Будь естественным и не дави на пользователя.",
    "reasoning": "обоснование, вся ли информация собрана",
    "internal_thoughts": "какие данные уже собраны и чего не хватает",
    "next_action": "continue_interview | propose_schema",
    "needs_more_info": true/false,
    "criteria_summary": "краткое резюме собранных критериев",
    "schema_proposal": "предложенная схема в формате JSON (только если needs_more_info=false)"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=1000
        )
        content = response.choices[0].message.content
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Interview error: {e}")
        raise ConnectionError("LLM is unavailable")

async def conduct_interview_basic(history: list) -> dict:
    """Basic version of interview without schema proposal for backward compatibility"""
    context_str = ""
    for msg in history[-5:]:  # Take last 5 messages
        role = "User" if msg["role"] == "user" else "Assistant"
        content = msg.get("content", "")
        context_str += f"{role}: {content}\n"

    prompt = f"""Ты — агент для глубокого анализа рынка. Твоя задача — собрать минимально необходимую информацию для поиска товаров и принять решение о переходе к следующему этапу.

ИСТОРИЯ:
{context_str}

КРИТЕРИИ ЗАВЕРШЕНИЯ ИНТЕРВЬЮ:
- Узнай бюджет (минимум диапазон или сумма)
- Узнай целевую категорию товара (ноутбук, смартфон и т.д.)
- Узнай основные характеристики (например, процессор, память, экран для ноутбука)
- Узнай предпочтения по состоянию (новый/б/у)
- Узнай предпочтения по брендам (если есть)

ИНСТРУКЦИЯ:
- Если в истории уже есть информация, удовлетворяющая критериям завершения, НЕ задавай повторные вопросы.
- Если вся необходимая информация собрана, сообщи пользователю об этом и предложи перейти к следующему этапу.
- Если информации недостаточно, задавай конкретные уточняющие вопросы.
- В поле "reasoning" кратко опиши, вся ли необходимая информация собрана.
- В поле "internal_thoughts" укажи, какие данные уже собраны и чего не хватает.
- Устанавливай "needs_more_info" в false, если вся необходимая информация собрана.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "response": "текст ответа пользователю - краткое резюме собранных данных и предложение перейти к следующему этапу, если вся информация собрана, или уточняющий вопрос, если информации недостаточно",
    "reasoning": "обоснование, вся ли информация собрана",
    "internal_thoughts": "какие данные уже собраны и чего не хватает",
    "needs_more_info": true/false,
    "criteria_summary": "краткое резюме собранных критериев"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=700
        )
        content = response.choices[0].message.content
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Interview error: {e}")
        raise ConnectionError("LLM is unavailable")

async def generate_schema_proposal(criteria: str) -> dict:
    """Generate a schema proposal based on gathered criteria"""
    prompt = f"""Создай JSON-схему для извлечения характеристик из объявлений на Avito.
КРИТЕРИИ ПОЛЬЗОВАТЕЛЯ: {criteria}

ИНСТРУКЦИЯ:
- Создай 5-8 полей, которые помогут отфильтровать товары по указанным критериям
- Используй только типы "str", "int", "float"
- Каждое поле должно иметь "type" и "desc" (описание)
- Схема должна позволить провести SQL-фильтрацию по критериям пользователя
- В поле "reasoning" кратко напиши ход своих мыслей.
- В поле "internal_thoughts" укажи внутренние размышления, почему ты принял то или иное решение.
- В поле "next_action" укажи следующее действие: "return_schema", "request_more_info", "modify_schema".

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "schema": "схема в формате JSON",
    "reasoning": "почему выбрано это действие",
    "internal_thoughts": "внутренние размышления о принятии решения",
    "next_action": "return_schema | request_more_info | modify_schema"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=800
        )
        res = response.choices[0].message.content
        if "```" in res:
            res = res.split("```")[1].replace("json", "").strip()
        parsed_res = json.loads(res)

        # Возвращаем словарь с самой схемой и рассуждениями
        return {
            "schema": json.dumps(parsed_res["schema"], ensure_ascii=False, indent=2),
            "reasoning": parsed_res.get("reasoning", ""),
            "internal_thoughts": parsed_res.get("internal_thoughts", ""),
            "next_action": parsed_res.get("next_action", "return_schema")
        }
    except Exception as e:
        print(f"Schema generation error: {e}")
        # Return a default schema with error information
        default_schema = {
            "brand": {"type": "str", "desc": "Бренд товара"},
            "model": {"type": "str", "desc": "Модель товара"},
            "price": {"type": "int", "desc": "Цена"},
            "condition": {"type": "str", "desc": "Состояние (новый/б/у)"},
            "year": {"type": "int", "desc": "Год выпуска"}
        }
        return {
            "schema": json.dumps(default_schema, ensure_ascii=False, indent=2),
            "reasoning": "Ошибка генерации схемы",
            "internal_thoughts": f"Произошла ошибка при генерации схемы: {e}",
            "next_action": "return_schema"
        }

async def generate_sql_query(criteria: str, schema_agreed: str) -> dict:
    """Generate SQL query based on user criteria and extraction schema"""
    try:
        schema = json.loads(schema_agreed) if isinstance(schema_agreed, str) else schema_agreed
        schema_fields = list(schema.keys())
    except:
        schema_fields = ["brand", "model", "price", "condition"]

    prompt = f"""Создай SQL-запрос для фильтрации товаров в базе данных SQLite.
КРИТЕРИИ ПОЛЬЗОВАТЕЛЯ: {criteria}
ДОСТУПНЫЕ ПОЛЯ В СХЕМЕ: {', '.join(schema_fields)}

ИНСТРУКЦИЯ:
- Запрос должен использовать таблицу 'item' с полем 'structured_data' (хранит JSON)
- Используй json_extract для извлечения значений из JSON
- Пример: json_extract(structured_data, '$.field_name')
- Фильтруй по критериям пользователя
- Сортируй по релевантности или цене
- Ограничь результат 20 лучшими вариантами
- В поле "reasoning" кратко напиши ход своих мыслей.
- В поле "internal_thoughts" укажи внутренние размышления, почему ты принял то или иное решение.
- В поле "next_action" укажи следующее действие: "execute_query", "modify_query", "request_more_info".
- Верни ТОЛЬКО JSON.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "sql_query": "SQL-запрос",
    "reasoning": "почему выбрано это действие",
    "internal_thoughts": "внутренние размышления о принятии решения",
    "next_action": "execute_query | modify_query | request_more_info"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=600
        )
        content = response.choices[0].message.content.strip()
        # Clean up the response if it contains extra text
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        result = json.loads(content)
        return result
    except Exception as e:
        print(f"SQL generation error: {e}")
        # Return a default query with error information
        return {
            "sql_query": f"SELECT * FROM item WHERE json_extract(structured_data, '$.price') IS NOT NULL ORDER BY json_extract(structured_data, '$.price') ASC LIMIT 20;",
            "reasoning": "Ошибка генерации SQL-запроса",
            "internal_thoughts": f"Произошла ошибка при генерации SQL-запроса: {e}",
            "next_action": "execute_query"
        }