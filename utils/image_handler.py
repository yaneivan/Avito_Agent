import hashlib
import os
from pathlib import Path
from config import IMAGE_STORAGE_PATH
from utils.logger import logger


def save_image_from_base64(image_base64: str, filename_prefix: str = "") -> str:
    """
    Сохраняет изображение из base64 строки и возвращает путь к файлу
    :param image_base64: строка изображения в формате base64
    :param filename_prefix: префикс для имени файла
    :return: путь к сохраненному файлу
    """
    if not image_base64:
        return None
    
    # Извлекаем данные из строки base64 (убираем префикс data:image/...)
    if image_base64.startswith('data:image'):
        header, encoded = image_base64.split(',', 1)
        # Определяем расширение из заголовка
        ext = header.split('/')[1].split(';')[0]
    else:
        # Если нет заголовка, предполагаем, что это pure base64
        encoded = image_base64
        ext = 'jpg'  # по умолчанию
    
    # Декодируем base64 строку
    import base64
    try:
        image_data = base64.b64decode(encoded)
    except Exception as e:
        logger.error(f"Ошибка декодирования base64 изображения: {e}")
        return None
    
    # Создаем директорию для изображений, если не существует
    os.makedirs(IMAGE_STORAGE_PATH, exist_ok=True)
    
    # Создаем хеш изображения для уникального имени файла
    image_hash = hashlib.md5(image_data).hexdigest()
    
    # Формируем имя файла
    if filename_prefix:
        filename = f"{filename_prefix}_{image_hash}.{ext}"
    else:
        filename = f"{image_hash}.{ext}"
    
    filepath = os.path.join(IMAGE_STORAGE_PATH, filename)
    
    # Проверяем, существует ли уже файл с таким хешем
    if os.path.exists(filepath):
        logger.info(f"Файл с таким хешем уже существует: {filepath}")
        return filepath
    
    # Сохраняем изображение
    try:
        with open(filepath, 'wb') as f:
            f.write(image_data)
        logger.info(f"Изображение сохранено: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Ошибка сохранения изображения: {e}")
        return None


def download_and_save_image(url: str, filename_prefix: str = "") -> str:
    """
    Скачивает и сохраняет изображение по URL
    :param url: URL изображения
    :param filename_prefix: префикс для имени файла
    :return: путь к сохраненному файлу
    """
    import requests
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        
        # Получаем расширение из URL или заголовков
        ext = Path(url).suffix.lower()[1:]  # убираем точку
        if not ext:
            # Пытаемся определить из заголовка Content-Type
            content_type = response.headers.get('Content-Type', '')
            if 'jpeg' in content_type or 'jpg' in content_type:
                ext = 'jpg'
            elif 'png' in content_type:
                ext = 'png'
            elif 'gif' in content_type:
                ext = 'gif'
            else:
                ext = 'jpg'  # по умолчанию
        
        # Создаем директорию для изображений, если не существует
        os.makedirs(IMAGE_STORAGE_PATH, exist_ok=True)
        
        # Создаем хеш изображения для уникального имени файла
        image_hash = hashlib.md5(response.content).hexdigest()
        
        # Формируем имя файла
        if filename_prefix:
            filename = f"{filename_prefix}_{image_hash}.{ext}"
        else:
            filename = f"{image_hash}.{ext}"
        
        filepath = os.path.join(IMAGE_STORAGE_PATH, filename)
        
        # Проверяем, существует ли уже файл с таким хешем
        if os.path.exists(filepath):
            logger.info(f"Файл с таким хешем уже существует: {filepath}")
            return filepath
        
        # Сохраняем изображение
        with open(filepath, 'wb') as f:
            f.write(response.content)
        
        logger.info(f"Изображение по URL сохранено: {filepath}")
        return filepath
    except Exception as e:
        logger.error(f"Ошибка при скачивании изображения по URL {url}: {e}")
        return None