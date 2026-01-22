# routers/__init__.py

from .chat import router as chat_router
from .deep_research import router as deep_research_router
from .tasks import router as tasks_router
from .views import router as views_router

# Объединяем их в список (необязательно, но удобно)
__all__ = ["chat_router", "deep_research_router", "tasks_router", "views_router"]