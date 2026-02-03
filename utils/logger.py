import logging
import sys
from pathlib import Path
from datetime import datetime
import re

# Создаем папку для логов, если её нет
logs_dir = Path("./logs")
logs_dir.mkdir(exist_ok=True)

# Функция для безопасной обработки текста с эмодзи и Unicode
def safe_text(text: str) -> str:
    """
    Безопасно обрабатывает текст, удаляя или заменяя проблемные символы.
    Сохраняет кириллицу, латиницу, основные пунктуационные знаки.
    """
    if not text:
        return ""
    
    try:
        # Сначала пытаемся просто вернуть текст
        return str(text)
    except Exception:
        return ""


# Функция для очистки эмодзи из сообщений (опционально, если нужно совсем убрать)
def remove_emojis(text: str) -> str:
    """Удаляет эмодзи из текста для корректного отображения в логах"""
    if not text:
        return ""
    
    try:
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
        return emoji_pattern.sub(r'', str(text))
    except Exception:
        return str(text)


# Пользовательский класс для безопасного вывода в консоль
class SafeConsoleHandler(logging.StreamHandler):
    """Безопасный обработчик для вывода в консоль с обработкой Unicode"""
    
    def __init__(self, stream=None):
        super().__init__(stream)
        # Устанавливаем UTF-8 для вывода
        if hasattr(self.stream, 'reconfigure'):
            try:
                self.stream.reconfigure(encoding='utf-8')
            except:
                pass
    
    def emit(self, record):
        try:
            # Сохраняем оригинальное сообщение
            original_msg = record.msg
            original_args = record.args
            
            try:
                # Формируем сообщение
                if record.args:
                    msg = record.msg % record.args
                else:
                    msg = record.msg
                
                # Безопасно обрабатываем сообщение
                safe_msg = safe_text(msg)
                
                # Создаем новую запись с безопасным сообщением
                record.msg = safe_msg
                record.args = ()
                
                # Пытаемся записать с обработкой ошибок
                try:
                    super().emit(record)
                except UnicodeEncodeError:
                    # Если не получается, пробуем записать байтами
                    stream = self.stream
                    if stream:
                        try:
                            stream.write(safe_msg + self.terminator)
                            self.flush()
                        except:
                            # Последняя попытка: записать как байты в буфер
                            stream.buffer.write((safe_msg + self.terminator).encode('utf-8', errors='replace'))
                            self.flush()
                            
            finally:
                # Восстанавливаем оригинальные значения
                record.msg = original_msg
                record.args = original_args
                
        except Exception:
            self.handleError(record)


# Пользовательский класс для безопасной записи в файл
class SafeFileHandler(logging.FileHandler):
    """Безопасный обработчик для записи в файл с обработкой Unicode"""
    
    def __init__(self, filename, mode='a', encoding='utf-8', delay=False):
        # Всегда используем UTF-8 для файлов
        super().__init__(filename, mode=mode, encoding=encoding, delay=delay)
    
    def emit(self, record):
        try:
            # Сохраняем оригинальное сообщение
            original_msg = record.msg
            original_args = record.args
            
            try:
                # Формируем сообщение
                if record.args:
                    msg = record.msg % record.args
                else:
                    msg = record.msg
                
                # Удаляем эмодзи из сообщения для файла (опционально)
                clean_msg = remove_emojis(msg)
                
                # Создаем новую запись
                record.msg = clean_msg
                record.args = ()
                
                # Вызываем базовый метод
                super().emit(record)
                
            finally:
                # Восстанавливаем оригинальные значения
                record.msg = original_msg
                record.args = original_args
                
        except Exception:
            self.handleError(record)


# Настройка форматирования логов
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Создаем форматтер
formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

# Настройка корневого логгера
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# Удаляем все существующие обработчики
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Создаем обработчики
console_handler = SafeConsoleHandler(sys.stdout)
console_handler.setFormatter(formatter)

file_handler = SafeFileHandler(
    f"./logs/app_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    encoding='utf-8'
)
file_handler.setFormatter(formatter)

# Добавляем обработчики к корневому логгеру
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

# Основной логгер
logger = logging.getLogger("market_research")
logger.setLevel(logging.INFO)


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
extension_file_handler = SafeFileHandler(
    f"./logs/extension_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    encoding='utf-8'
)
extension_formatter = logging.Formatter('%(asctime)s [%(levelname)s] %(name)s: %(message)s')
extension_file_handler.setFormatter(extension_formatter)

extension_logger.addHandler(extension_file_handler)
extension_logger.propagate = False  # Не передавать сообщения в родительские логгеры


# Функция для безопасного логирования с любыми символами
def safe_log(logger_instance, level, message, *args, **kwargs):
    """Безопасно логирует сообщение, обрабатывая Unicode символы"""
    try:
        if args:
            formatted_msg = message % args
        else:
            formatted_msg = message
        
        # Безопасно обрабатываем сообщение
        safe_msg = safe_text(formatted_msg)
        
        # Логируем
        if level == logging.INFO:
            logger_instance.info(safe_msg, **kwargs)
        elif level == logging.ERROR:
            logger_instance.error(safe_msg, **kwargs)
        elif level == logging.WARNING:
            logger_instance.warning(safe_msg, **kwargs)
        elif level == logging.DEBUG:
            logger_instance.debug(safe_msg, **kwargs)
        else:
            logger_instance.log(level, safe_msg, **kwargs)
    except Exception as e:
        # В крайнем случае логируем ошибку логирования
        try:
            logger_instance.error(f"Logging error: {e}")
        except:
            pass


# Обертка для удобного использования
class SafeLogger:
    """Безопасный логгер с обработкой Unicode"""
    
    def __init__(self, name):
        self.logger = logging.getLogger(name)
    
    def info(self, msg, *args, **kwargs):
        safe_log(self.logger, logging.INFO, msg, *args, **kwargs)
    
    def error(self, msg, *args, **kwargs):
        safe_log(self.logger, logging.ERROR, msg, *args, **kwargs)
    
    def warning(self, msg, *args, **kwargs):
        safe_log(self.logger, logging.WARNING, msg, *args, **kwargs)
    
    def debug(self, msg, *args, **kwargs):
        safe_log(self.logger, logging.DEBUG, msg, *args, **kwargs)


# Создаем безопасные логгеры
safe_logger = SafeLogger("market_research")
safe_extension_logger = SafeLogger("extension")


# --- НАСТРОЙКА ФИЛЬТРОВ ДЛЯ UVICORN ---
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        # Скрываем успешные (200 OK) запросы к /api/get_task
        if "/api/get_task" in msg and "204" in msg:
            return False
        if "market_research" in msg and "200" in msg:
            return False
        return True


# Применяем фильтр для uvicorn access логов
uvicorn_access = logging.getLogger("uvicorn.access")
uvicorn_access.addFilter(EndpointFilter())


# Экспортируем основные логгеры
__all__ = [
    'logger',
    'extension_logger',
    'safe_logger',
    'safe_extension_logger',
    'get_logger',
    'safe_log'
]