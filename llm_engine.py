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

async def check_confirmation(user_input: str) -> bool:
    print(f"[DEBUG LLM] Checking confirmation for: {user_input}")
    prompt = f"Пользователь сказал: '{user_input}'. Это согласие (да, давай, ок, подтверждаю) или отказ/изменение? JSON: {{ 'confirmed': true/false }}"
    try:
        res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], temperature=0.1)
        data = json.loads(clean_json(res.choices[0].message.content))
        print(f"[DEBUG LLM] Confirmed: {data.get('confirmed')}")
        return data.get("confirmed", False)
    except: return False

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

async def evaluate_relevance(title: str, desc: str, price: str, img_path: str, criteria: str) -> dict:
    # print(f"[DEBUG LLM] Evaluating: {title}") # Слишком много спама, если включить
    prompt = f"""Оцени товар: "{title}", цена: {price}. Запрос: "{criteria}".
1. relevance_score: 0 (совсем не то), 1 (плохо), 2 (норм), 3 (супер).
2. visual_notes: опиши дефекты или состояние кратко.
JSON: {{ 'relevance_score': int, 'visual_notes': str, 'specs': {{}} }}"""
    
    msg = [{"type": "text", "text": prompt}]
    b64 = encode_image_to_base64(img_path)
    if b64: msg.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
    
    try:
        res = await client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": msg}], temperature=0.1)
        return json.loads(clean_json(res.choices[0].message.content))
    except Exception as e:
        print(f"[ERROR LLM] Eval relevance: {e}")
        return {"relevance_score": 1, "visual_notes": "Ошибка анализа", "specs": {}}

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