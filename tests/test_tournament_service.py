import pytest
from unittest.mock import patch, Mock
from services.tournament_service import tournament_ranking, rank_group
import pytest
from unittest.mock import patch, Mock
from services.tournament_service import tournament_ranking, rank_group

def test_tournament_ranking_complex():
    # Реалистичные ID из базы данных
    lot1 = {'id': 145, 'title': 'GPU A'}
    lot2 = {'id': 210, 'title': 'GPU B'}
    lot3 = {'id': 305, 'title': 'GPU C'}
    lot4 = {'id': 412, 'title': 'GPU D'}

    # Группы с перекрытием (lot2 и lot3 участвуют дважды)
    lot_groups = [
        [lot1, lot2, lot3],
        [lot2, lot3, lot4]
    ]
    
    criteria = "price"

    with patch('services.tournament_service.rank_group') as mock_rank:
        # В первой группе: C(3), B(2), A(1)
        # Во второй группе: D(3), C(2), B(1)
        mock_rank.side_effect = [
            [lot3, lot2, lot1], 
            [lot4, lot3, lot2]
        ]
        
        result = tournament_ranking(lot_groups, criteria)

        # Проверка нормализации (средний балл)
        # lot3: (3 + 2) / 2 = 2.5
        # lot4: 3 / 1 = 3.0 (Топ-1)
        # lot2: (2 + 1) / 2 = 1.5
        # lot1: 1 / 1 = 1.0
        
        assert result[0]['id'] == 412
        assert result[1]['id'] == 305
        assert result[2]['id'] == 210
        assert result[3]['id'] == 145
        assert result[1]['tournament_score'] == 2.5

def test_rank_group_mapping():
    group = [
        {'id': 999, 'title': 'Target'}, # local ID 1
        {'id': 888, 'title': 'Other'}   # local ID 2
    ]
    
    with patch('services.tournament_service.get_completion') as mock_llm:
        resp = Mock()
        resp.content = "1, 2" # LLM выбрала первый по списку (999)
        mock_llm.return_value = resp
        
        ranked = rank_group(group, "any")
        
        # Проверяем, что локальная "1" превратилась в объект с ID 999
        assert ranked[0]['id'] == 999
        assert len(ranked) == 2

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
        assert all('id' in item and 'tournament_score' in item for item in result)

        # Проверяем, что товары отсортированы по убыванию оценки
        scores = [item['tournament_score'] for item in result]
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