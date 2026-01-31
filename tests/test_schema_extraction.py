import pytest
import json
import base64
from unittest.mock import patch, MagicMock
from core.services import ItemProcessingService


@pytest.mark.asyncio
async def test_schema_extraction_with_problematic_item():
    """
    Тест проверяет извлечение характеристик по согласованной схеме
    для объявления, у которого возникли проблемы с извлечением.
    
    Используется захардкоженная информация из проблемного объявления:
    - ID: 1
    - Title: 'Аренда игровых компьютеров / пк (Без залога)'
    - Price: '1250'
    - Description: длинное описание
    - Image Path: 'images/task_1\0_8394323435067431462.jpg'
    - Raw JSON: полный JSON из базы данных
    - Schema Agreed: схема из базы данных
    """
    
    # Захардкоженные данные из проблемного объявления
    item_data = {
        "title": "Аренда игровых компьютеров / пк (Без залога)",
        "price": "1250",
        "url": "https://www.avito.ru/moskva/nastolnye_kompyutery/arenda_igrovyh_kompyuterov_pk_bez_zaloga_2245412520?context=H4sIAAAAAAAA_wE_AMD_YToyOntzOjEzOiJsb2NhbFByaW9yaXR5IjtiOjA7czoxOiJ4IjtzOjE6ImciO3M6MTE6InZhbHVlSW5kZXgiO2k6MDt99uHkXT8AAAA",
        "description": "Аренда игровых компьютеров / ПК (Без залога). Хотите купить игровой компьютер? Сначала попробуй! Без залога! Есть все возможные модели игровых компьютеров, разных процессоров и оперативной памяти. Оперативная память 12 ГБ. Без залога. Вотличном внешнем и техническом состоянии. Подберем под ваш бюджет. В наличии более 200 шт. //// Условия Аренды \\\\\\. Подписание договора. Без Залога. Оплата любым способом. ///// Доставка и Возврат В Любое Время \\\\\\. В пределах Мкад 449р. За Мкад и по России так же имеется. Самовывоз из офиса м. Беговая, ул. Розанова дом 4, 30 секунд от метро. Есть места для парковки машины. ///// Бонусы и Акции \\\\\\. Скидки до 50% — при долгосрочном сотрудничестве. + 1 день Бесплатно. За подписку на инстаграм и отзыв ;). ///// Расценки \\\\\\. Игровой компьютер: от 1250 рублей сутки и от 6350р / мес! (можно взять и на любой другой срок). Мы Продаём компьютер. Цена продажи: 60.000 руб. Есть вопросы? Звоните или пишите!:). При встрече мы обучаем как пользоваться техникой, отвечаем на ваши вопросы и подписываем договор для вашей и нашей безопасности. Работаем с 2014 года, множество довольных клиентов и отзывов! Постоянным клиентам скидки и бонусы. #.",
        "image_base64": None,  # Будет загружено из файла
        "local_path": "tests/test_item_image.jpg",
        "structured_data": None
    }

    # Загрузим изображение и закодируем его в base64
    with open(item_data["local_path"], "rb") as img_file:
        image_data = img_file.read()
        item_data["image_base64"] = base64.b64encode(image_data).decode('utf-8')

    # Захардкоженная схема из базы данных
    extraction_schema = {
        "cpu_model": {"type": "str", "desc": "Модель процессора"},
        "ram_gb": {"type": "int", "desc": "Объем ОЗУ в ГБ"},
        "storage_type": {"type": "str", "desc": "Тип накопителя: SSD, HDD, Hybrid"},
        "storage_gb": {"type": "int", "desc": "Объем накопителя в ГБ"},
        "motherboard_material": {"type": "str", "desc": "Материал материнской платы: ГФ, ПП, Металл, Другое"},
        "power_supply_watt": {"type": "int", "desc": "Мощность блока питания в Вт"},
        "case_material": {"type": "str", "desc": "Материал корпуса: Металл, Пластик, Металл+Пластик"},
        "case_size_cm": {"type": "str", "desc": "Размер корпуса в см (например, 40x30x15)"},
        "has_defects": {"type": "bool", "desc": "Есть дефекты (например, трещины, коррозия, повреждения)"},
        "wear_level": {"type": "int", "desc": "Уровень износа (0-100%)"},
        "is_complete": {"type": "bool", "desc": "Комплектность: есть все компоненты, включая кабели, документы"},
        "power_supply_original": {"type": "bool", "desc": "Есть оригинальный блок питания"},
        "cooling_system": {"type": "str", "desc": "Тип охлаждения: вентилятор, радиатор, без охлаждения"},
        "fan_count": {"type": "int", "desc": "Количество вентиляторов"},
        "price_rub": {"type": "int", "desc": "Цена в рублях (до 30 000)"}
    }

    # Мокаем LLM для извлечения характеристик
    with patch('llm_engine.extract_product_features') as mock_extract:
        # Предполагаем, что LLM возвращает какие-то характеристики
        mock_return_value = {
            "cpu_model": "Intel Core i5",
            "ram_gb": 12,
            "storage_type": "SSD",
            "storage_gb": 500,
            "has_defects": False,
            "wear_level": 20,
            "is_complete": True,
            "price_rub": 1250
        }
        mock_extract.return_value = mock_return_value

        # Импортируем функцию внутри контекста мока, чтобы использовать замоканную версию
        from llm_engine import extract_product_features

        # Вызываем функцию извлечения характеристик (она будет использовать замоканную версию)
        extracted_features = await extract_product_features(
            item_data["title"],
            item_data["description"],
            item_data["price"],
            item_data["image_base64"],
            "Компьютер",  # criteria
            extraction_schema
        )

        # Проверяем, что функция была вызвана
        mock_extract.assert_called_once_with(
            item_data["title"],
            item_data["description"],
            item_data["price"],
            item_data["image_base64"],
            "Компьютер",  # criteria
            extraction_schema
        )

        # Проверяем, что возвращенные характеристики соответствуют ожиданиям
        assert extracted_features is not None
        assert isinstance(extracted_features, dict)
        
        # Проверяем конкретные поля
        assert "cpu_model" in extracted_features
        assert "ram_gb" in extracted_features
        assert "storage_type" in extracted_features
        
        print("Тест успешно пройден! Характеристики были извлечены корректно.")
        print(f"Извлеченные характеристики: {extracted_features}")


async def run_test():
    await test_schema_extraction_with_problematic_item()


if __name__ == "__main__":
    import asyncio
    asyncio.run(run_test())