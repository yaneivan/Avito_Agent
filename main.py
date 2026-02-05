"""
Основной файл запуска приложения
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from api.router import router
import uvicorn

class NoCacheStaticFiles(StaticFiles):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

app = FastAPI(title="Avito Agent")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене укажите конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")

# Подключаем статические файлы для нашего нового фронтенда
app.mount("/frontend", NoCacheStaticFiles(directory="frontend"), name="frontend")
app.mount("/images", NoCacheStaticFiles(directory="data/images"), name="images")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8001)