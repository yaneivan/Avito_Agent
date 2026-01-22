# services/__init__.py

# Импортируем классы из файлов, чтобы они были доступны как services.ProcessingService
from .processing import ProcessingService, ChatProcessingService
from .orchestrator import DeepResearchOrchestrator