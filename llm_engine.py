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
            "reply": "Я готов помочь. Что ищем?", 
            "reasoning": "Ошибка парсинга",
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