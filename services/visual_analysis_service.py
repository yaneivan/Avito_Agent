from typing import Tuple
from utils.llm_client import get_completion
from utils.image_handler import save_image_from_base64
from utils.logger import logger
import base64


class VisualAnalysisService:
    def __init__(self):
        pass

    def analyze_visual_features(self, image_path: str) -> Tuple[str, str]:
        """
        Анализирует визуальные особенности изображения с помощью LLM
        :param image_path: путь к изображению
        :return: (визуальные заметки, описание изображения)
        """
        logger.info(f"Анализируем визуальные особенности изображения: {image_path}")
        
        try:
            # Читаем изображение и конвертируем в base64
            with open(image_path, "rb") as img_file:
                img_data = base64.b64encode(img_file.read()).decode()
            
            # Подготовим сообщение для LLM
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Опиши детали изображения товара. Укажи цвет, размер, состояние, бренд, модель, особенности дизайна и любые другие визуально различимые характеристики."},
                        {"type": "image_url", "image_url": f"data:image/jpeg;base64,{img_data}"}
                    ]
                }
            ]
            
            # Вызываем LLM для анализа изображения
            response = get_completion(messages)
            
            visual_notes = response.content
            
            # Формируем описание изображения
            image_desc = f"Изображение товара: {visual_notes}"
            
            logger.info(f"Визуальный анализ завершен: {image_path}")
            return visual_notes, image_desc
        except Exception as e:
            logger.error(f"Ошибка при визуальном анализе изображения {image_path}: {e}")
            return "", f"Изображение товара: невозможно проанализировать ({str(e)})"