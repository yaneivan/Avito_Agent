import re
from typing import List, Dict, Any
from utils.logger import logger
from utils.llm_client import get_completion

def tournament_ranking(lot_groups: List[List[Dict[str, Any]]], criteria: str) -> List[Dict[str, Any]]:
    """
    Турнирный реранкинг товаров по системе Борда с нормализацией.
    
    :param lot_groups: Группы лотов (по 5 шт) с перекрытием.
    :param criteria: Критерии для сравнения.
    :return: Отсортированный список исходных объектов лотов.
    """
    logger.info(f"Начало турнира: {len(lot_groups)} групп")

    # Собираем статистику: сумма баллов и количество участий
    # lot_stats = { id: {"sum": total_points, "count": appearances, "data": original_dict} }
    lot_stats: Dict[str, Dict[str, Any]] = {}

    for group_idx, group in enumerate(lot_groups):
        logger.info(f"Обработка группы {group_idx + 1}/{len(lot_groups)}")
        
        # 1. Ранжируем группу через LLM
        ranked_group = rank_group(group, criteria)

        # 2. Начисляем баллы Борда (1-е место = N баллов, последнее = 1 балл)
        n = len(ranked_group)
        for position, lot in enumerate(ranked_group):
            # Важно: используем реальный ID из базы
            lot_id = str(lot.get('id'))
            if not lot_id or lot_id == "None":
                logger.error(f"Критическая ошибка: у лота отсутствует ID в группе {group_idx}")
                continue

            points = n - position

            if lot_id not in lot_stats:
                lot_stats[lot_id] = {"sum": 0, "count": 0, "data": lot}
            
            lot_stats[lot_id]["sum"] += points
            lot_stats[lot_id]["count"] += 1

    # 3. Нормализация (вычисляем средний балл)
    final_list = []
    for lot_id, stats in lot_stats.items():
        avg_score = stats["sum"] / stats["count"]
        # Сохраняем средний балл в объект для отладки/отображения
        lot_data = stats["data"]
        lot_data["tournament_score"] = round(avg_score, 2)
        final_list.append(lot_data)

    # 4. Финальная сортировка по среднему баллу
    sorted_result = sorted(final_list, key=lambda x: x["tournament_score"], reverse=True)
    
    logger.info(f"Турнир завершен. Отранжировано {len(sorted_result)} уникальных лотов")
    return sorted_result


def rank_group(group: List[Dict[str, Any]], criteria: str) -> List[Dict[str, Any]]:
    """
    Ранжирование конкретной группы лотов. 
    В случае ошибки парсинга возвращает исходную группу (чтобы не ломать весь поиск).
    """
    # Подготавливаем расширенный контекст для LLM (включая визуальные заметки)
    items_description = []
    for i, item in enumerate(group):
        desc = (
            f"ID: {i+1}\n"
            f"Title: {item.get('title')}\n"
            f"Price: {item.get('price')}\n"
            f"Characteristics: {item.get('structured_data')}\n"
            f"Visual analysis: {item.get('image_description_and_notes')}\n"
            f"Relevance: {item.get('relevance')}\n"
        )
        items_description.append(desc)

    full_items_text = "\n---\n".join(items_description)

    prompt = f"""
Compare these items based on criteria: {criteria}

Items to rank:
{full_items_text}

Rank them from BEST to WORST. Return ONLY the IDs separated by commas.
Example: 3, 1, 5, 2, 4
"""

    messages = [
        {"role": "system", "content": "You are a professional market analyst. Rank items strictly by criteria. Return ONLY a comma-separated list of numeric IDs."},
        {"role": "user", "content": prompt}
    ]

    try:
        response = get_completion(messages)
        content = response.content.strip()
        
        # Надежный парсинг: вытаскиваем все числа из ответа
        found_ids = [int(x) for x in re.findall(r'\d+', content)]
        
        # Валидация: убираем дубли и проверяем границы индексов
        seen = set()
        valid_indices = []
        for idx in found_ids:
            # Превращаем ID (1-based) в индекс (0-based)
            actual_idx = idx - 1
            if 0 <= actual_idx < len(group) and actual_idx not in seen:
                valid_indices.append(actual_idx)
                seen.add(actual_idx)

        # Формируем список объектов в новом порядке
        ranked_items = [group[i] for i in valid_indices]

        # Добавляем потерянные лоты (если LLM кого-то забыла) в конец
        if len(ranked_items) < len(group):
            missing_items = [item for i, item in enumerate(group) if i not in seen]
            ranked_items.extend(missing_items)
            logger.warning(f"LLM пропустила {len(missing_items)} лотов при ранжировании, они добавлены в конец")

        return ranked_items

    except Exception as e:
        logger.error(f"Ошибка при вызове LLM в rank_group: {e}", exc_info=True)
        # В случае сбоя возвращаем как было, чтобы не прерывать процесс
        return group