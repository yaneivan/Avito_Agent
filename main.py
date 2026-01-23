import os
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import create_db_and_tables
from contextlib import asynccontextmanager

from routers import chat, deep_research, tasks, views

# --- НАСТРОЙКА ЛОГОВ ---
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Скрываем успешные (200 OK) запросы к системным эндпоинтам и статике
        if "/api/get_task" in msg and "200" in msg: return False
        if "GET /api/chats" in msg and "200" in msg: return False
        if "GET /api/searches" in msg and "200" in msg: return False
        if "GET /images" in msg and "200" in msg: return False
        if "POST /api/log" in msg and "200" in msg: return False
        return True

# Применяем фильтр
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- SERVER STARTUP ---")
    create_db_and_tables()
    os.makedirs("images", exist_ok=True)
    yield

app = FastAPI(lifespan=lifespan)

app.mount("/images", StaticFiles(directory="images"), name="images")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

app.include_router(views.router)
app.include_router(chat.router)
app.include_router(deep_research.router)
app.include_router(tasks.router)

if __name__ == "__main__":
    import uvicorn
    # Запускаем на 8002
    uvicorn.run(app, host="0.0.0.0", port=8002, reload=False)