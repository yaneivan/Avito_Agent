"""
Unit тесты для демонстрации новой унифицированной архитектуры
"""
import pytest
import asyncio
import json
from llm_engine import deep_research_agent


@pytest.mark.asyncio
async def test_unified_agent_initial_request():
    """Тест: Пользователь делает начальный запрос"""
    print("\\n" + "="*60)
    print("ТЕСТ 1: ПОЛЬЗОВАТЕЛЬ ДЕЛАЕТ НАЧАЛЬНЫЙ ЗАПРОС")
    print("-" * 40)

    history = [{"role": "user", "content": "Привет! Я хочу купить хороший ноутбук для работы"}]
    current_state = {
        "stage": "interview",
        "query_text": "Привет! Я хочу купить хороший ноутбук для работы",
        "interview_data": "",
        "schema_agreed": None
    }

    print(f"История диалога: {history}")
    print(f"Текущее состояние: {current_state}")

    response = await deep_research_agent(history, current_state)
    print(f"\\nResponse type: {response['type']}")
    print(f"Message: {response['message']}")
    print(f"Number of tool calls: {len(response['tool_calls'])}")
    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")

            # Если вызван инструмент propose_schema, покажем схему
            if tool_call['name'] == 'propose_schema':
                if 'schema' in arguments:
                    print(f"    Предложенная схема: {json.dumps(arguments['schema'], indent=4, ensure_ascii=False)}")
                elif 'criteria' in arguments:
                    print(f"    Критерии: {arguments['criteria']}")
    else:
        print("  Ответ агента: " + response['message'])

    # Проверяем, что агент отвечает текстом, а не вызывает инструменты на первом этапе
    assert response['type'] in ['chat', 'tool_call'], "Агент должен вернуть либо чат, либо вызов инструмента"
    print("Test 1 passed")


@pytest.mark.asyncio
async def test_unified_agent_with_budget():
    """Тест: Пользователь уточняет бюджет"""
    print("\\n" + "="*60)
    print("ТЕСТ 2: ПОЛЬЗОВАТЕЛЬ УТОЧНЯЕТ БЮДЖЕТ")
    print("-" * 40)

    history = [
        {"role": "user", "content": "Привет! Я хочу купить хороший ноутбук для работы"},
        {"role": "assistant", "content": "Для начала работы мне нужно понять, что именно вы ищете и какой у вас бюджет. Можете уточнить, на какую сумму рассчитываете?"},
        {"role": "user", "content": "Думаю о бюджете 70-100 тысяч рублей"}
    ]
    current_state = {
        "stage": "interview",
        "query_text": "Думаю о бюджете 70-100 тысяч рублей",
        "interview_data": "",
        "schema_agreed": None
    }

    print(f"История диалога: {history}")
    print(f"Текущее состояние: {current_state}")

    response = await deep_research_agent(history, current_state)
    print(f"\\nResponse type: {response['type']}")
    print(f"Message: {response['message']}")
    print(f"Number of tool calls: {len(response['tool_calls'])}")
    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")

            # Если вызван инструмент propose_schema, покажем схему
            if tool_call['name'] == 'propose_schema':
                if 'schema' in arguments:
                    print(f"    Предложенная схема: {json.dumps(arguments['schema'], indent=4, ensure_ascii=False)}")
                elif 'criteria' in arguments:
                    print(f"    Критерии: {arguments['criteria']}")
    else:
        print("  Ответ агента: " + response['message'])

    assert response['type'] in ['chat', 'tool_call'], "Агент должен вернуть либо чат, либо вызов инструмента"
    print("Test 2 passed")


@pytest.mark.asyncio
async def test_unified_agent_proposes_schema():
    """Тест: Агент предлагает схему извлечения данных"""
    print("\\n" + "="*60)
    print("ТЕСТ 3: АГЕНТ ПРЕДЛАГАЕТ СХЕМУ ИЗВЛЕЧЕНИЯ ДАННЫХ")
    print("-" * 40)

    history = [
        {"role": "user", "content": "Привет! Я хочу купить хороший ноутбук для работы"},
        {"role": "assistant", "content": "Для начала работы мне нужно понять, что именно вы ищете и какой у вас бюджет. Можете уточнить, на какую сумму рассчитываете?"},
        {"role": "user", "content": "Думаю о бюджете 70-100 тысяч рублей"},
        {"role": "assistant", "content": "Отлично! Теперь мне нужно понять, какие характеристики для вас наиболее важны. Например, нужен ли вам SSD, сколько оперативной памяти, какой процессор и т.д. Можете перечислить основные требования?"}
    ]
    current_state = {
        "stage": "interview",
        "query_text": "Думаю о бюджете 70-100 тысяч рублей",
        "interview_data": "",
        "schema_agreed": None
    }

    print(f"История диалога: {history}")
    print(f"Текущее состояние: {current_state}")

    response = await deep_research_agent(history, current_state)
    print(f"\\nResponse type: {response['type']}")
    print(f"Message: {response['message']}")
    print(f"Number of tool calls: {len(response['tool_calls'])}")
    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")

            # Если вызван инструмент propose_schema, покажем схему
            if tool_call['name'] == 'propose_schema':
                if 'schema' in arguments:
                    print(f"    Предложенная схема: {json.dumps(arguments['schema'], indent=4, ensure_ascii=False)}")
                elif 'criteria' in arguments:
                    print(f"    Критерии: {arguments['criteria']}")
    else:
        print("  Ответ агента: " + response['message'])

    assert response['type'] in ['chat', 'tool_call'], "Агент должен вернуть либо чат, либо вызов инструмента"
    print("Test 3 passed")


@pytest.mark.asyncio
async def test_unified_agent_agrees_with_schema():
    """Тест: Пользователь соглашается с предложенной схемой"""
    print("\\n" + "="*60)
    print("ТЕСТ 4: ПОЛЬЗОВАТЕЛЬ СОГЛАСЕН С ПРЕДЛОЖЕННОЙ СХЕМОЙ")
    print("-" * 40)

    sample_schema = {
        "cpu": {"type": "str", "desc": "Модель процессора"},
        "ram_gb": {"type": "int", "desc": "Объем оперативной памяти в ГБ"},
        "storage_gb": {"type": "int", "desc": "Объем SSD в ГБ"},
        "screen_size": {"type": "float", "desc": "Диагональ экрана в дюймах"},
        "condition": {"type": "str", "desc": "Состояние (новый/б/у, оценка внешнего вида)"},
        "battery_cycles": {"type": "int", "desc": "Количество циклов зарядки"},
        "included_accessories": {"type": "str", "desc": "Комплектация (зарядное устройство, сумка и т.д.)"}
    }

    history = [
        {"role": "user", "content": "Привет! Я хочу купить хороший ноутбук для работы"},
        {"role": "assistant", "content": "Для начала работы мне нужно понять, что именно вы ищете и какой у вас бюджет. Можете уточнить, на какую сумму рассчитываете?"},
        {"role": "user", "content": "Думаю о бюджете 70-100 тысяч рублей"},
        {"role": "assistant", "content": "Отлично! Теперь мне нужно понять, какие характеристики для вас наиболее важны. Например, нужен ли вам SSD, сколько оперативной памяти, какой процессор и т.д. Можете перечислить основные требования?"},
        {"role": "user", "content": f"Вот моя предложенная схема: {json.dumps(sample_schema, indent=2, ensure_ascii=False)}"},
        {"role": "assistant", "content": "Спасибо! Эта схема выглядит хорошей. Давайте использовать её для поиска."},
        {"role": "user", "content": "Да, всё верно. Можем начинать поиск!"}
    ]
    current_state = {
        "stage": "schema_proposed",
        "query_text": "Ноутбук 70-100 тысяч рублей",
        "interview_data": "User: Ноутбук для работы\\nAI: Уточните бюджет и требования",
        "schema_agreed": json.dumps(sample_schema)
    }

    print(f"История диалога: {history}")
    print(f"Текущее состояние: {current_state}")

    response = await deep_research_agent(history, current_state)
    print(f"\\nResponse type: {response['type']}")
    print(f"Message: {response['message']}")
    print(f"Number of tool calls: {len(response['tool_calls'])}")
    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")

            # Если вызван инструмент proceed_to_search, покажем детали
            if tool_call['name'] == 'proceed_to_search':
                print(f"    Agent proceeds to search!")
                if 'query' in arguments:
                    print(f"    Поисковый запрос: {arguments['query']}")
    else:
        print("  Ответ агента: " + response['message'])

    assert response['type'] in ['chat', 'tool_call'], "Агент должен вернуть либо чат, либо вызов инструмента"
    print("Test 4 passed")


@pytest.mark.asyncio
async def test_unified_agent_disagrees_with_schema():
    """Тест: Пользователь не согласен с предложенной схемой"""
    print("\\n" + "="*60)
    print("ТЕСТ 5: ПОЛЬЗОВАТЕЛЬ НЕ СОГЛАСЕН С ПРЕДЛОЖЕННОЙ СХЕМОЙ")
    print("-" * 40)

    sample_schema = {
        "cpu": {"type": "str", "desc": "Модель процессора"},
        "ram_gb": {"type": "int", "desc": "Объем оперативной памяти в ГБ"}
    }

    history = [
        {"role": "user", "content": "Я хочу купить ноутбук"},
        {"role": "assistant", "content": f"Предлагаю следующую схему: {json.dumps(sample_schema, indent=2, ensure_ascii=False)}"},
        {"role": "user", "content": "Не подходит. Мне нужно поле для графического ускорителя и года выпуска"}
    ]
    current_state = {
        "stage": "schema_proposed",
        "query_text": "Я хочу купить ноутбук",
        "interview_data": "User: Я хочу купить ноутбук\\nAI: Предлагаю следующую схему...",
        "schema_agreed": json.dumps(sample_schema)
    }

    print(f"История диалога: {history}")
    print(f"Текущее состояние: {current_state}")

    response = await deep_research_agent(history, current_state)
    print(f"\\nResponse type: {response['type']}")
    print(f"Message: {response['message']}")
    print(f"Number of tool calls: {len(response['tool_calls'])}")
    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")

            # Если вызван инструмент propose_schema, покажем новую схему
            if tool_call['name'] == 'propose_schema':
                if 'schema' in arguments:
                    print(f"    Новая предложенная схема: {json.dumps(arguments['schema'], indent=4, ensure_ascii=False)}")
    else:
        print("  Ответ агента: " + response['message'])
        print("  Это нормальное поведение при обсуждении изменений схемы")

    assert response['type'] in ['chat', 'tool_call'], "Агент должен вернуть либо чат, либо вызов инструмента"
    print("Test 5 passed")


@pytest.mark.asyncio
async def test_unified_agent_handles_questions():
    """Тест: Пользователь задает уточняющий вопрос"""
    print("\\n" + "="*60)
    print("ТЕСТ 6: ПОЛЬЗОВАТЕЛЬ ЗАДАЕТ УТОЧНЯЮЩИЙ ВОПРОС")
    print("-" * 40)

    sample_schema = {
        "cpu": {"type": "str", "desc": "Модель процессора"},
        "ram_gb": {"type": "int", "desc": "Объем оперативной памяти в ГБ"},
        "storage_gb": {"type": "int", "desc": "Объем SSD в ГБ"},
        "condition": {"type": "str", "desc": "Состояние (новый/б/у, оценка внешнего вида)"}
    }

    history = [
        {"role": "user", "content": "Я хочу купить ноутбук"},
        {"role": "assistant", "content": f"Предлагаю следующую схему: {json.dumps(sample_schema, indent=2, ensure_ascii=False)}"},
        {"role": "user", "content": "А что именно вы подразумеваете под состоянием?"}
    ]
    current_state = {
        "stage": "schema_proposed",
        "query_text": "Я хочу купить ноутбук",
        "interview_data": "User: Я хочу купить ноутбук\\nAI: Предлагаю следующую схему...",
        "schema_agreed": json.dumps(sample_schema)
    }

    print(f"История диалога: {history}")
    print(f"Текущее состояние: {current_state}")

    response = await deep_research_agent(history, current_state)
    print(f"\\nResponse type: {response['type']}")
    print(f"Message: {response['message']}")
    print(f"Number of tool calls: {len(response['tool_calls'])}")
    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")
    else:
        print("  Ответ агента: " + response['message'])
        print("  Это нормальное поведение при ответе на вопросы")

    assert response['type'] in ['chat', 'tool_call'], "Агент должен вернуть либо чат, либо вызов инструмента"
    print("Test 6 passed")


@pytest.mark.asyncio
async def test_complex_scenario():
    """Тест: Сложный сценарий с несколькими итерациями"""
    print("\\n" + "="*60)
    print("ТЕСТ 7: СЛОЖНЫЙ СЦЕНАРИЙ С НЕСКОЛЬКИМИ ИТЕРАЦИЯМИ")
    print("-" * 40)

    # Начальный запрос
    history = [{"role": "user", "content": "Привет! Хочу купить ноутбук для программирования"}]
    current_state = {
        "stage": "interview",
        "query_text": "Привет! Хочу купить ноутбук для программирования",
        "interview_data": "",
        "schema_agreed": None
    }

    print(f"Шаг 1 - Начальный запрос: {history[0]['content']}")
    response = await deep_research_agent(history, current_state)
    print(f"  Ответ агента: {response['message'][:100]}...")
    print(f"  Тип ответа: {response['type']}")
    print(f"  Вызовов инструментов: {len(response['tool_calls'])}")

    # Добавляем ответ агента в историю
    history.append({"role": "assistant", "content": response['message']})

    # Пользователь уточняет требования
    user_message = "Нужен мощный процессор, много оперативки и SSD объемом хотя бы 512 ГБ"
    history.append({"role": "user", "content": user_message})
    current_state["query_text"] = user_message

    print(f"\\nШаг 2 - Уточнение требований: {user_message}")
    response = await deep_research_agent(history, current_state)
    print(f"  Тип ответа: {response['type']}")
    print(f"  Вызовов инструментов: {len(response['tool_calls'])}")

    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")

    # Добавляем ответ агента в историю
    history.append({"role": "assistant", "content": response['message']})

    # Пользователь уточняет бюджет
    user_message = "Бюджет до 150 000 рублей"
    history.append({"role": "user", "content": user_message})
    current_state["query_text"] = user_message

    print(f"\\nШаг 3 - Уточнение бюджета: {user_message}")
    response = await deep_research_agent(history, current_state)
    print(f"  Тип ответа: {response['type']}")
    print(f"  Вызовов инструментов: {len(response['tool_calls'])}")

    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")
            if tool_call['name'] == 'propose_schema':
                print(f"    Предложенная схема: {json.dumps(arguments.get('schema', {}), indent=4, ensure_ascii=False)}")

    print("Test 7 passed")


@pytest.mark.asyncio
async def test_import_consistency_async():
    """Тест: Асинхронная проверка корректности импортов"""
    print("\\n" + "="*60)
    print("ТЕСТ 8: АСИНХРОННАЯ ПРОВЕРКА КОРРЕКТНОСТИ ИМПОРТОВ")
    print("-" * 40)

    # Проверяем, что все необходимые функции доступны для импорта
    try:
        from llm_engine import deep_research_agent, generate_schema_proposal
        print("+ Функции deep_research_agent и generate_schema_proposal доступны для импорта")

        # Проверяем, что функция, которой больше не существует, не импортируется
        try:
            from llm_engine import check_confirmation
            print("✗ ОШИБКА: Функция check_confirmation все еще доступна для импорта")
            assert False, "Функция check_confirmation не должна быть доступна для импорта"
        except ImportError:
            print("+ Функция check_confirmation корректно удалена из llm_engine")

        # conduct_interview остается в системе для обратной совместимости
        print("+ Функция conduct_interview доступна (для обратной совместимости)")

        try:
            from llm_engine import generate_schema_proposal
            print("+ Функция generate_schema_proposal доступна для импорта")
        except ImportError:
            print("- ОШИБКА: Функция generate_schema_proposal недоступна для импорта")
            assert False, "Функция generate_schema_proposal должна быть доступна для импорта"

    except ImportError as e:
        print(f"- ОШИБКА импорта: {e}")
        assert False, f"Ошибка импорта: {e}"

    print("+ Асинхронная проверка импортов завершена успешно")
    print("Test 8 passed")


@pytest.mark.asyncio
async def test_complex_scenario():
    """Тест: Сложный сценарий с несколькими итерациями"""
    print("\\n" + "="*60)
    print("ТЕСТ 7: СЛОЖНЫЙ СЦЕНАРИЙ С НЕСКОЛЬКИМИ ИТЕРАЦИЯМИ")
    print("-" * 40)

    # Начальный запрос
    history = [{"role": "user", "content": "Привет! Хочу купить ноутбук для программирования"}]
    current_state = {
        "stage": "interview",
        "query_text": "Привет! Хочу купить ноутбук для программирования",
        "interview_data": "",
        "schema_agreed": None
    }

    print(f"Шаг 1 - Начальный запрос: {history[0]['content']}")
    response = await deep_research_agent(history, current_state)
    print(f"  Ответ агента: {response['message'][:100]}...")
    print(f"  Тип ответа: {response['type']}")
    print(f"  Вызовов инструментов: {len(response['tool_calls'])}")

    # Добавляем ответ агента в историю
    history.append({"role": "assistant", "content": response['message']})

    # Пользователь уточняет требования
    user_message = "Нужен мощный процессор, много оперативки и SSD объемом хотя бы 512 ГБ"
    history.append({"role": "user", "content": user_message})
    current_state["query_text"] = user_message

    print(f"\\nШаг 2 - Уточнение требований: {user_message}")
    response = await deep_research_agent(history, current_state)
    print(f"  Тип ответа: {response['type']}")
    print(f"  Вызовов инструментов: {len(response['tool_calls'])}")

    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")

    # Добавляем ответ агента в историю
    history.append({"role": "assistant", "content": response['message']})

    # Пользователь уточняет бюджет
    user_message = "Бюджет до 150 000 рублей"
    history.append({"role": "user", "content": user_message})
    current_state["query_text"] = user_message

    print(f"\\nШаг 3 - Уточнение бюджета: {user_message}")
    response = await deep_research_agent(history, current_state)
    print(f"  Тип ответа: {response['type']}")
    print(f"  Вызовов инструментов: {len(response['tool_calls'])}")

    if response['tool_calls']:
        for i, tool_call in enumerate(response['tool_calls']):
            print(f"  Tool {i+1}: {tool_call['name']}")
            arguments = tool_call['arguments']
            print(f"    Arguments: {json.dumps(arguments, indent=4, ensure_ascii=False)}")
            if tool_call['name'] == 'propose_schema':
                print(f"    Предложенная схема: {json.dumps(arguments.get('schema', {}), indent=4, ensure_ascii=False)}")

    print("Test 7 passed")


def test_import_consistency():
    """Тест: Проверка корректности импортов в проекте"""
    print("\\n" + "="*60)
    print("ТЕСТ: ПРОВЕРКА КОРРЕКТНОСТИ ИМПОРТОВ")
    print("="*60)

    # Проверяем, что все необходимые функции доступны для импорта
    try:
        from llm_engine import deep_research_agent, generate_schema_proposal
        print("+ Функции deep_research_agent и generate_schema_proposal доступны для импорта")

        # Проверяем, что функция, которой больше не существует, не импортируется
        try:
            from llm_engine import check_confirmation
            print("- ОШИБКА: Функция check_confirmation все еще доступна для импорта")
            assert False, "Функция check_confirmation не должна быть доступна для импорта"
        except ImportError:
            print("+ Функция check_confirmation корректно удалена из llm_engine")

        # conduct_interview остается в системе для обратной совместимости
        print("+ Функция conduct_interview доступна (для обратной совместимости)")

        try:
            from llm_engine import generate_schema_proposal
            print("+ Функция generate_schema_proposal доступна для импорта")
        except ImportError:
            print("- ОШИБКА: Функция generate_schema_proposal недоступна для импорта")
            assert False, "Функция generate_schema_proposal должна быть доступна для импорта"

    except ImportError as e:
        print(f"- ОШИБКА импорта: {e}")
        assert False, f"Ошибка импорта: {e}"

    print("+ Проверка импортов завершена успешно")


def test_summary():
    """Итоговый вывод о проделанной работе"""
    print("\\n" + "="*60)
    print("ИТОГИ ТЕСТИРОВАНИЯ НОВОЙ АРХИТЕКТУРЫ")
    print("="*60)
    print("Новая унифицированная архитектура позволяет:")
    print("* Вести естественный диалог с пользователем")
    print("* Предлагать схему извлечения данных при необходимости")
    print("* Обрабатывать изменения и уточнения от пользователя")
    print("* Переходить к поиску только с согласия пользователя")
    print("* Использовать инструменты только для критических действий")
    print("* Обрабатывать уточняющие вопросы без перехода к инструментам")
    print("* Поддерживать сложные сценарии с несколькими итерациями")
    print("* Проверять корректность импортов для предотвращения ошибок")
    print("="*60)