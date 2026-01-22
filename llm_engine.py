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
- Если action: "chat", то search_query, limit и schema_name ДОЛЖНЫ БЫТЬ null.
- Если создаешь новую схему, дай ей короткое имя на английском.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "reasoning": "почему выбрано это действие",
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
            max_tokens=400
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
- Верни чистый JSON."""

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
            max_tokens=800,
            temperature=0.0
        )
        res = response.choices[0].message.content
        if "```" in res: 
            res = res.split("```")[1].replace("json", "").strip()
        return json.loads(res)
    except Exception as e:
        print(f"LOG ERROR Extraction: {e}")
        return {"notes": "Ошибка извлечения данных"}

async def generate_schema_structure(topic: str) -> str:
    prompt = f"""Создай простую JSON схему (5-6 полей) для извлечения данных о товарах типа '{topic}'.
Используй только типы "str", "int", "float".
Каждое поле должно иметь "type" и "desc".
Верни ТОЛЬКО чистый JSON."""
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400
        )
        res = response.choices[0].message.content
        if "```" in res: 
            res = res.split("```")[1].replace("json", "").strip()
        json.loads(res) # Валидация
        return res
    except:
        return json.dumps({
            "brand": {"type": "str", "desc": "Бренд"},
            "model": {"type": "str", "desc": "Модель"},
            "condition": {"type": "str", "desc": "Состояние"}
        })

async def summarize_search_results(query: str, items: list) -> str:
    if not items:
        return "Поиск не дал результатов."

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

Будь краток, не пиши приветствий. Максимум 150-200 слов."""
    
    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1000
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Ошибка при создании отчета: {e}"

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

    prompt = f"""Ты — интервьюер для глубокого анализа рынка.
Твоя задача: задавать уточняющие вопросы пользователю, чтобы собрать полный портрет его потребностей.

ИСТОРИЯ:
{context_str}

ИНСТРУКЦИЯ:
- Задавай уточняющие вопросы: бюджет, предпочтения по характеристикам, состояние, бренды, критичные дефекты и т.д.
- Не начинай поиск сразу, собирай информацию.
- После каждого ответа пользователя оценивай, достаточно ли информации для формирования схемы извлечения.
- Когда информации достаточно, предложи схему извлечения данных в виде текстового описания.
- Отвечай в формате JSON.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "response": "текст вопроса или ответа, может включать предложение схемы, когда информация достаточна",
    "needs_more_info": true/false,
    "criteria_summary": "краткое резюме собранных критериев",
    "schema_proposal": "предложенная схема в формате JSON (только когда needs_more_info=false)"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=800
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

    prompt = f"""Ты — интервьюер для глубокого анализа рынка.
Твоя задача: задавать уточняющие вопросы пользователю, чтобы собрать полный портрет его потребностей.

ИСТОРИЯ:
{context_str}

ИНСТРУКЦИЯ:
- Задавай уточняющие вопросы: бюджет, предпочтения по характеристикам, состояние, бренды, критичные дефекты и т.д.
- Не начинай поиск сразу, собирай информацию.
- После каждого ответа пользователя оценивай, достаточно ли информации для формирования схемы извлечения.
- Отвечай в формате JSON.

ОТВЕТЬ ТОЛЬКО JSON:
{{
    "response": "текст вопроса или ответа",
    "needs_more_info": true/false,
    "criteria_summary": "краткое резюме собранных критериев"
}}"""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=500
        )
        content = response.choices[0].message.content
        if "```" in content:
            content = content.split("```")[1].replace("json", "").strip()
        return json.loads(content)
    except Exception as e:
        print(f"Interview error: {e}")
        raise ConnectionError("LLM is unavailable")

async def generate_schema_proposal(criteria: str) -> str:
    """Generate a schema proposal based on gathered criteria"""
    prompt = f"""Создай JSON-схему для извлечения характеристик из объявлений на Avito.
КРИТЕРИИ ПОЛЬЗОВАТЕЛЯ: {criteria}

ИНСТРУКЦИЯ:
- Создай 5-8 полей, которые помогут отфильтровать товары по указанным критериям
- Используй только типы "str", "int", "float"
- Каждое поле должно иметь "type" и "desc" (описание)
- Схема должна позволить провести SQL-фильтрацию по критериям пользователя
- Верни ТОЛЬКО чистый JSON-объект схемы."""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=600
        )
        res = response.choices[0].message.content
        if "```" in res:
            res = res.split("```")[1].replace("json", "").strip()
        parsed_res = json.loads(res)
        return json.dumps(parsed_res, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Schema generation error: {e}")
        # Return a default schema
        default_schema = {
            "brand": {"type": "str", "desc": "Бренд товара"},
            "model": {"type": "str", "desc": "Модель товара"},
            "price": {"type": "int", "desc": "Цена"},
            "condition": {"type": "str", "desc": "Состояние (новый/б/у)"},
            "year": {"type": "int", "desc": "Год выпуска"}
        }
        return json.dumps(default_schema, ensure_ascii=False, indent=2)

async def generate_sql_query(criteria: str, schema_json: str) -> str:
    """Generate SQL query based on user criteria and extraction schema"""
    try:
        schema = json.loads(schema_json) if isinstance(schema_json, str) else schema_json
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
- Верни ТОЛЬКО SQL-запрос без дополнительного текста."""

    try:
        response = await client.chat.completions.create(
            model=MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=400
        )
        sql_query = response.choices[0].message.content.strip()
        # Clean up the response if it contains extra text
        if "```" in sql_query:
            sql_query = sql_query.split("```")[1].replace("sql", "").strip()
        return sql_query
    except Exception as e:
        print(f"SQL generation error: {e}")
        # Return a default query
        return f"SELECT * FROM item WHERE json_extract(structured_data, '$.price') IS NOT NULL ORDER BY json_extract(structured_data, '$.price') ASC LIMIT 20;"