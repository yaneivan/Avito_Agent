import pytest
from unittest.mock import patch, mock_open
from utils.image_handler import save_image_from_base64
import os
import base64


def test_save_image_from_base64_success():
    """Тест успешного сохранения изображения из base64"""
    import os
    from pathlib import Path

    # Читаем реальное изображение из папки tests/images
    # Используем абсолютный путь, чтобы избежать проблем с рабочей директорией
    current_dir = Path(__file__).parent
    image_path = current_dir / "images" / "gaming_pc.jpg"

    # Проверяем, что файл существует
    assert image_path.exists(), f"Изображение не найдено: {image_path}"

    # Конвертируем изображение в base64
    with open(image_path, "rb") as img_file:
        img_data = img_file.read()
        img_base64 = base64.b64encode(img_data).decode()

    base64_str = f"data:image/jpeg;base64,{img_base64}"

    # Создаем временный каталог для тестов
    test_dir = "./test_images"
    os.makedirs(test_dir, exist_ok=True)

    # Меняем директорию на временную для теста
    original_cwd = os.getcwd()
    os.chdir(test_dir)

    try:
        result = save_image_from_base64(base64_str, "test")

        # Проверяем, что функция вернула путь к файлу
        assert result is not None
        assert "test_" in result
        # Проверяем, что файл имеет правильное расширение (jpg или jpeg)
        assert (result.endswith(".jpg") or result.endswith(".jpeg"))

        # Проверяем, что файл действительно существует
        assert os.path.exists(result)
    finally:
        # Возвращаем исходную директорию
        os.chdir(original_cwd)

        # Удаляем тестовую директорию
        import shutil
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)


def test_save_image_from_base64_empty():
    """Тест сохранения пустого изображения"""
    result = save_image_from_base64("")
    assert result is None


def test_save_image_from_base64_invalid():
    """Тест сохранения некорректного изображения"""
    result = save_image_from_base64("invalid_base64_string")
    assert result is None