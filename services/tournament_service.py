import re
from typing import List, Dict, Any
from utils.logger import logger
from utils.llm_client import get_completion

def tournament_ranking(lot_groups: List[List[Dict[str, Any]]], criteria: str, context: str = "") -> List[Dict[str, Any]]:
    logger.info(f"Начало турнира: {len(lot_groups)} групп. Контекст: {context}")

    lot_stats: Dict[str, Dict[str, Any]] = {}

    for group_idx, group in enumerate(lot_groups):
        logger.info(f"Обработка группы {group_idx + 1}/{len(lot_groups)}")
        
        ranked_group = rank_group(group, criteria, context)

        n = len(ranked_group)
        for position, lot in enumerate(ranked_group):
            lot_id = str(lot.get('id'))
            if not lot_id or lot_id == "None":
                logger.error(f"Критическая ошибка: у лота отсутствует ID в группе {group_idx}")
                continue

            points = n - position

            if lot_id not in lot_stats:
                lot_stats[lot_id] = {"sum": 0, "count": 0, "data": lot}
            
            lot_stats[lot_id]["sum"] += points
            lot_stats[lot_id]["count"] += 1

    final_list = []
    for lot_id, stats in lot_stats.items():
        avg_score = stats["sum"] / stats["count"]
        lot_data = stats["data"]
        lot_data["tournament_score"] = round(avg_score, 2)
        final_list.append(lot_data)

    sorted_result = sorted(final_list, key=lambda x: x["tournament_score"], reverse=True)
    
    logger.info(f"Турнир завершен. Отранжировано {len(sorted_result)} уникальных лотов")
    return sorted_result


def rank_group(group: List[Dict[str, Any]], criteria: str, context: str = "") -> List[Dict[str, Any]]:
    items_description = []
    for i, item in enumerate(group):
        desc = (
            f"Local ID: {i+1}\n"
            f"Title: {item.get('title')}\n"
            f"Price: {item.get('price')}\n"
            f"Characteristics: {item.get('structured_data')}\n"
            f"Visual analysis: {item.get('image_description_and_notes')}\n"
            f"Relevance: {item.get('relevance')}\n"
        )
        items_description.append(desc)

    full_items_text = "\n---\n".join(items_description)

    prompt = f"""
You are a professional market analyst.
User's main goal: {context}
Detailed ranking criteria: {criteria}

Items to rank:
{full_items_text}

INSTRUCTIONS:
1. First, perform a REASONING step: for each item, explain briefly why it matches or doesn't match the user's goal.
2. If an item is NOT what the user asked for (e.g. SSD instead of HDD), rank it at the very bottom.
3. Finally, output the ranked list of Local IDs from BEST to WORST.
4. Your response MUST end with the marker 'RANKING:' followed by the IDs.

Example response:
Reasoning:
- Item 1 is perfect because...
- Item 2 is a wrong device type...
RANKING: 1, 3, 2
"""

    messages = [
        {"role": "system", "content": "You provide expert market analysis. Always use the RANKING: marker at the end."},
        {"role": "user", "content": prompt}
    ]

    try:
        response = get_completion(messages)
        content = response.content.strip()
        
        logger.info(f"Промпт для группы:\n{prompt}")
        logger.info(f"----------------------------")
        logger.info(f"Полный ответ LLM для группы:\n{content}")

        if "RANKING:" not in content:
            logger.warning("Маркер RANKING: не найден в ответе LLM. Пытаюсь парсить весь текст.")
            ranking_part = content
        else:
            ranking_part = content.split("RANKING:")[-1]

        found_ids = [int(x) for x in re.findall(r'\d+', ranking_part)]
        
        seen = set()
        valid_indices = []
        for idx in found_ids:
            actual_idx = idx - 1
            if 0 <= actual_idx < len(group) and actual_idx not in seen:
                valid_indices.append(actual_idx)
                seen.add(actual_idx)

        ranked_items = [group[i] for i in valid_indices]

        if len(ranked_items) < len(group):
            missing_items = [item for i, item in enumerate(group) if i not in seen]
            ranked_items.extend(missing_items)
            logger.warning(f"Лоты { [i+1 for i in range(len(group)) if i not in seen] } были пропущены в RANKING:, добавлены в конец.")

        logger.info(f"Итоговый порядок Local IDs: {[group.index(item)+1 for item in ranked_items]}")
        return ranked_items

    except Exception as e:
        logger.error(f"Ошибка в rank_group: {e}", exc_info=True)
        return group