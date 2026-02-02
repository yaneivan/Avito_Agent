from typing import List, Dict, Any
from utils.logger import logger
from utils.llm_client import get_completion


def tournament_ranking(lot_groups: List[List[Dict]], criteria: str) -> List[Dict]:
    """
    Турнирный реранкинг товаров по критериям

    :param lot_groups: Группы лотов для сравнения (по 5 штук)
    :param criteria: Критерии для сравнения
    :return: Отсортированные лоты по рейтингу
    """
    logger.info(f"Начинаем турнирный реранкинг для {len(lot_groups)} групп")

    # Словарь для хранения итоговых баллов
    total_scores = {}

    # Обрабатываем каждую группу
    for group_idx, group in enumerate(lot_groups):
        logger.info(f"Обрабатываем группу {group_idx + 1}/{len(lot_groups)}, размер: {len(group)}")

        # Ранжируем товары в группе с использованием LLM
        ranked_group = rank_group(group, criteria)

        # Применяем систему голосования по Борда
        for position, lot in enumerate(ranked_group):
            lot_id = lot.get('id', f"{group_idx}_{position}")  # Уникальный ID для товара
            score = len(ranked_group) - position  # Чем выше место, тем больше баллов

            if lot_id in total_scores:
                total_scores[lot_id] += score
            else:
                total_scores[lot_id] = score

    # Сортируем товары по итоговым баллам
    sorted_lots = sorted(total_scores.items(), key=lambda x: x[1], reverse=True)

    logger.info(f"Турнирный реранкинг завершен, всего уникальных товаров: {len(sorted_lots)}")

    # Возвращаем отсортированные лоты с их итоговыми баллами
    result = []
    for lot_id, score in sorted_lots:
        # В реальной реализации здесь нужно будет получить полные данные о лоте
        result.append({
            'id': lot_id,
            'score': score,
            'original_data': {}  # Здесь будут полные данные о лоте
        })

    return result


def rank_group(group: List[Dict], criteria: str) -> List[Dict]:
    """
    Ранжирование товаров внутри группы с использованием LLM

    :param group: Группа товаров для ранжирования
    :param criteria: Критерии для сравнения
    :return: Ранжированная группа товаров (от лучшего к худшему)
    """
    logger.info(f"Ранжируем группу из {len(group)} товаров по критериям: {criteria}")

    # Формируем промпт для LLM
    products_info = "\n".join([
        f"{i+1}. {item.get('title', 'Без названия')} - {item.get('price', 'Цена не указана')}" +
        (f"\n   Характеристики: {item.get('structured_data', {})}" if item.get('structured_data') else "")
        for i, item in enumerate(group)
    ])

    prompt = f"""
    Товары для сравнения:
    {products_info}

    Критерии оценки: {criteria}

    Оцени товары по заданным критериям и расположи их по порядку от лучшего к худшему.
    Возвращай только номера товаров в порядке убывания качества (лучший первый),
    разделяя их запятыми. Например: 2, 1, 4, 3, 5
    """

    messages = [
        {"role": "system", "content": "Ты помощник в сравнении товаров. Пользователь предоставит тебе список товаров и критерии оценки. Верни только номера товаров в порядке убывания качества (лучший первый), разделяя их запятыми."},
        {"role": "user", "content": prompt}
    ]

    try:
        response = get_completion(messages)
        ranking_str = response.content.strip()

        # Парсим ответ, содержащий номера товаров
        ranked_indices = [int(x.strip()) - 1 for x in ranking_str.split(',') if x.strip().isdigit()]

        # Проверяем, что все индексы в допустимом диапазоне
        ranked_items = []
        for idx in ranked_indices:
            if 0 <= idx < len(group):
                ranked_items.append(group[idx])

        # Добавляем оставшиеся товары, если какие-то были пропущены
        ranked_item_ids = {id(item) for item in ranked_items}
        for item in group:
            if id(item) not in [id(i) for i in ranked_items]:
                ranked_items.append(item)

        logger.info(f"Группа из {len(group)} товаров успешно отранжирована")
        return ranked_items
    except Exception as e:
        logger.error(f"Ошибка при ранжировании группы товаров: {e}")
        # В случае ошибки возвращаем исходный порядок
        return group