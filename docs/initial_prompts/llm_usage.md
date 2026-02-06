Horsepower в проекте Avito Agent будет являться модель qwen3 vl 4b
Маленькая, неумная модель, с поддержкой ввода изображений. 
Развернута в docker, llama-cpp, openai-like. 
Инструкции должны быть подробными, детальными. 
Если какая-то оценка моделью должна выполниться, то критерии максимально четко описаны в промпте. 

LOCAL_LLM_URL=http://localhost:8080/v1
LOCAL_LLM_API_KEY=not-needed
LOCAL_LLM_MODEL=Qwen3-Vl-4B-Instruct


Желательно как можно больше использовать Sturctured outputs по pydantic схеме. 
```
from openai import OpenAI
from pydantic import BaseModel

client = OpenAI()

class CalendarEvent(BaseModel):
    name: str
    date: str
    participants: list[str]

response = client.responses.parse(
    model="gpt-4o-2024-08-06",
    input=[
        {"role": "system", "content": "Extract the event information."},
        {
            "role": "user",
            "content": "Alice and Bob are going to a science fair on Friday.",
        },
    ],
    text_format=CalendarEvent,
)

event = response.output_parsed
```

Парсить tool calls лучше текстом. В документации этой модели написано что hermes формат хорошо работает.
Валидация аргументов через pydantic. 
В случае, если аргументы неверные, подробно объясняем это в ошибке, возвращаем модели, даем ей еще один шанс сгенерировать вызов. 
Такой:
```
<tool_call>
{
  "name": "get_stock_price",
  "arguments": {
    "symbol": "AAPL"
  }
}
</tool_call>
```

Перечисление инструментов
```
<tools>
[
    {
        "name": "get_current_weather",
        "description": "Get the current weather in a given location",
        "parameters": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA"
                },
                "unit": {
                    "type": "string",
                    "enum": ["celsius", "fahrenheit"]
                }
            },
            "required": ["location"]
        }
    }
]
</tools>
```

Этот формат поддерживает выдачу текста и вызова функций вперемешку. Поэтому нужно этим пользоваться. Чтобы в чате шло не чисто вызов функции, а более главно типа "хорошо сейчас я изучу <вызов функции>"