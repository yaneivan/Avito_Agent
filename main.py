import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from database import create_db_and_tables
from contextlib import asynccontextmanager

# Импорт новых роутеров
from routers import chat, deep_research, tasks, views

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("--- SERVER STARTUP ---")
    create_db_and_tables()
    os.makedirs("images", exist_ok=True)
    yield

app = FastAPI(lifespan=lifespan)

# Монтирование статики (картинки)
app.mount("/images", StaticFiles(directory="images"), name="images")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Подключение маршрутов
app.include_router(views.router)
app.include_router(chat.router)
app.include_router(deep_research.router)
app.include_router(tasks.router)

if __name__ == "__main__":
    import uvicorn
    # Запуск сервера
    uvicorn.run(app, host="0.0.0.0", port=8001, reload=False)