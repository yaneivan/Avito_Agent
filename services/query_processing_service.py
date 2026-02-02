from utils.logger import logger


class QueryProcessingService:
    """
    Этот класс больше не используется в новой архитектуре.
    Логика обработки запросов теперь находится в ChatService
    с использованием единого вызова LLM с инструментами.
    """

    def __init__(self):
        logger.warning("QueryProcessingService больше не используется. "
                      "Логика обработки запросов теперь в ChatService.")