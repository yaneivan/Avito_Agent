import abc
import json
import base64
import os
from typing import Type, Any, Dict
from pydantic import BaseModel
from openai import AsyncOpenAI

# Абстрактный класс (Интерфейс)
class LLMProvider(abc.ABC):
    @abc.abstractmethod
    async def extract_data(self, 
                           text_content: str, 
                           image_path: str | None, 
                           schema: Type[BaseModel]) -> BaseModel:
        pass

# 1. Провайдер для OpenAI (Structured Outputs)
class OpenAIStrictProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str = None, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def extract_data(self, text_content: str, image_path: str | None, schema: Type[BaseModel]) -> BaseModel:
        messages = [
            {"role": "system", "content": "Extract structured data from the listing. Use the supplied JSON schema."},
            {"role": "user", "content": [{"type": "text", "text": text_content}]}
        ]
        
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

        # МАГИЯ OPENAI: .parse()
        completion = await self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=schema, # Передаем Pydantic класс напрямую
        )
        return completion.choices[0].message.parsed

# 2. Универсальный провайдер (Ollama, OpenRouter, Llama.cpp)
class GenericProvider(LLMProvider):
    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key, base_url=base_url)
        self.model = model

    async def extract_data(self, text_content: str, image_path: str | None, schema: Type[BaseModel]) -> BaseModel:
        # Для обычных моделей нужно превратить Pydantic в JSON Schema текстом
        json_schema_str = json.dumps(schema.model_json_schema(), indent=2)
        
        prompt = (
            f"Analyze the item data.\n"
            f"Extract details according to this JSON Schema:\n{json_schema_str}\n\n"
            f"Return ONLY valid JSON matching the schema."
        )
        
        messages = [
            {"role": "system", "content": "You are a data extraction assistant. Output JSON only."},
            {"role": "user", "content": [{"type": "text", "text": prompt + "\n\nData:\n" + text_content}]}
        ]

        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
                messages[1]["content"].append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}"}
                })

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            response_format={"type": "json_object"}, # Просим JSON mode
            temperature=0.1
        )
        
        raw_json = response.choices[0].message.content
        # Валидируем через Pydantic (если мусор, то упадет ошибка, которую мы поймаем выше)
        return schema.model_validate_json(raw_json)

# Фабрика провайдеров
def get_llm_provider() -> LLMProvider:
    # Здесь логика выбора. Можно брать из конфига.
    # Пример для локальной Llama/Qwen:
    return GenericProvider(
        api_key="not-needed",
        base_url="http://localhost:8080/v1", 
        model="qwen3-vl"
    )
    
    # Пример для OpenAI:
    # return OpenAIStrictProvider(api_key=os.getenv("OPENAI_API_KEY"))