import pytest
from unittest.mock import patch, Mock
from services.tournament_service import tournament_ranking, rank_group


def test_tournament_ranking():
    """Тест турнирного реранкинга"""
    # Создаем тестовые группы товаров
    lot_groups = [
        [
            {'id': 1, 'title': 'Товар 1', 'price': '1000', 'structured_data': {'rating': 4}},
            {'id': 2, 'title': 'Товар 2', 'price': '1500', 'structured_data': {'rating': 5}},
            {'id': 3, 'title': 'Товар 3', 'price': '1200', 'structured_data': {'rating': 3}}
        ],
        [
            {'id': 4, 'title': 'Товар 4', 'price': '2000', 'structured_data': {'rating': 4}},
            {'id': 5, 'title': 'Товар 5', 'price': '1800', 'structured_data': {'rating': 2}},
            {'id': 6, 'title': 'Товар 6', 'price': '2200', 'structured_data': {'rating': 5}}
        ]
    ]
    
    criteria = "по рейтингу и цене"
    
    # Мокаем функцию rank_group, чтобы она возвращала предсказуемый результат
    with patch('services.tournament_service.rank_group') as mock_rank_group:
        # Возвращаем товары в обратном порядке (лучший последним в каждой группе)
        mock_rank_group.side_effect = lambda group, criteria: list(reversed(group))
        
        result = tournament_ranking(lot_groups, criteria)
        
        # Проверяем, что результат содержит оценки
        assert len(result) == 6  # 6 товаров в двух группах
        assert all('id' in item and 'score' in item for item in result)
        
        # Проверяем, что товары отсортированы по убыванию оценки
        scores = [item['score'] for item in result]
        assert scores == sorted(scores, reverse=True)


def test_rank_group():
    """Тест ранжирования группы товаров"""
    group = [
        {'id': 1, 'title': 'Товар 1', 'price': '1000', 'structured_data': {'rating': 4}},
        {'id': 2, 'title': 'Товар 2', 'price': '1500', 'structured_data': {'rating': 5}},
        {'id': 3, 'title': 'Товар 3', 'price': '1200', 'structured_data': {'rating': 3}}
    ]
    
    criteria = "по рейтингу"
    
    # Мокаем вызов LLM
    with patch('services.tournament_service.get_completion') as mock_llm:
        mock_response = Mock()
        # Предполагаем, что LLM возвращает номера товаров в порядке убывания качества
        # В данном случае: товар 2 (рейтинг 5) -> товар 1 (рейтинг 4) -> товар 3 (рейтинг 3)
        mock_response.content = "2, 1, 3"
        mock_llm.return_value = mock_response
        
        ranked_group = rank_group(group, criteria)
        
        # Проверяем, что товары отранжированы правильно
        assert len(ranked_group) == 3
        assert ranked_group[0]['id'] == 2  # Лучший товар (рейтинг 5)
        assert ranked_group[1]['id'] == 1  # Второй товар (рейтинг 4)
        assert ranked_group[2]['id'] == 3  # Худший товар (рейтинг 3)


def test_rank_group_with_error():
    """Тест обработки ошибки при ранжировании группы товаров"""
    group = [
        {'id': 1, 'title': 'Товар 1', 'price': '1000'},
        {'id': 2, 'title': 'Товар 2', 'price': '1500'}
    ]
    
    criteria = "по качеству"
    
    # Мокаем вызов LLM, чтобы он вызвал исключение
    with patch('services.tournament_service.get_completion', side_effect=Exception("LLM Error")):
        ranked_group = rank_group(group, criteria)
        
        # При ошибке возвращается исходный порядок
        assert len(ranked_group) == 2
        assert ranked_group[0]['id'] == 1
        assert ranked_group[1]['id'] == 2