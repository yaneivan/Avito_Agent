import os
import base64

def save_base64_image(image_base64: str, task_id: int, index: int, url: str) -> str | None:
    """
    Декодирует base64 и сохраняет картинку на диск.
    Возвращает путь к файлу или None, если ошибка.
    """
    if not image_base64:
        return None

    try:
        # Папка задачи
        task_dir = f"images/task_{task_id}"
        os.makedirs(task_dir, exist_ok=True)

        # Разделяем заголовок и данные
        if "," in image_base64:
            header, encoded = image_base64.split(",", 1)
        else:
            header, encoded = None, image_base64
        
        # Определяем расширение
        file_ext = "jpg"
        if header:
            if "png" in header: file_ext = "png"
            elif "webp" in header: file_ext = "webp"
        
        # Генерируем безопасное имя файла
        # Используем хэш URL, чтобы имя было уникальным, но коротким
        url_hash = abs(hash(url))
        filename = f"{index}_{url_hash}.{file_ext}"
        filepath = os.path.join(task_dir, filename)
        
        # Записываем
        with open(filepath, "wb") as f:
            f.write(base64.b64decode(encoded))
        
        return filepath

    except Exception as e:
        print(f"Error saving image for {url}: {e}")
        return None