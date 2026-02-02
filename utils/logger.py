import logging
import sys
from pathlib import Path
from datetime import datetime

# Создаем папку для логов, если её нет
logs_dir = Path("./logs")
logs_dir.mkdir(exist_ok=True)

# Функция для очистки эмодзи из сообщений
def remove_emojis(text: str) -> str:
    """Удаляет эмодзи из текста для корректного отображения в логах"""
    import re
    # Регулярное выражение для поиска эмодзи
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags (iOS)
        "\U00002500-\U00002BEF"  # chinese char
        "\U00002702-\U000027B0"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"  # dingbats
        "\u3030"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub(r'', text)

# Настройка форматирования логов
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

# Пользовательский класс для обработки логов с очисткой эмодзи
class EmojiFreeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        # Сохраняем оригинальное сообщение
        original_msg = record.msg
        original_args = record.args

        # Формируем сообщение с аргументами, как это делает базовый класс
        if record.args:
            formatted_msg = record.msg % record.args
        else:
            formatted_msg = record.msg

        # Очищаем от эмодзи
        clean_msg = remove_emojis(formatted_msg)

        # Устанавливаем очищенное сообщение
        record.msg = clean_msg
        record.args = ()

        # Вызываем базовый метод emit
        super().emit(record)

        # Восстанавливаем оригинальные значения
        record.msg = original_msg
        record.args = original_args

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[
        logging.FileHandler(f"./logs/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"),
        EmojiFreeStreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def get_logger(name: str) -> logging.Logger:
    """
    Возвращает настроенный логгер с указанным именем
    :param name: имя логгера
    :return: экземпляр логгера
    """
    return logging.getLogger(name)

# Создаем отдельный логгер для сообщений браузерного расширения
extension_logger = logging.getLogger('extension')
extension_logger.setLevel(logging.INFO)

# Создаем обработчик для записи в отдельный файл
extension_handler = logging.FileHandler(f"./logs/extension_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
extension_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
extension_handler.setFormatter(extension_formatter)

extension_logger.addHandler(extension_handler)
extension_logger.propagate = False  # Не передавать сообщения в родительские логгеры

# --- НАСТРОЙКА ЛОГОВ ---
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Скрываем успешные (200 OK) запросы к /api/get_task
        if "/api/get_task" in msg and "204" in msg: return False
        return True

# Применяем фильтр
logging.getLogger("uvicorn.access").addFilter(EndpointFilter())