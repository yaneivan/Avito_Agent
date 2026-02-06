/**
 * Основной модуль приложения
 */

// Объект состояния приложения
const state = {
    mr_id: null,              // ID текущего исследования
    chat_history: [],         // Полная история чата
    currentStatus: 'CHAT',    // Текущий статус (CHAT, SEARCHING_QUICK и т.д.)
    lastChatUpdateId: 0       // ID последнего обновления чата для отслеживания изменений
};

/**
 * Инициализация приложения
 */
function initApp() {
    console.log('Инициализация приложения...');

    // Привязываем обработчики событий
    bindEventListeners();

    // Настраиваем обработчик polling
    setupPollingHandler();

    // Показываем приветственное сообщение
    showWelcomeMessage();

    // Фокус на поле ввода
    document.getElementById('message-input').focus();
}

/**
 * Привязка обработчиков событий
 */
function bindEventListeners() {
    // Отправка сообщения по кнопке
    document.getElementById('send-btn').addEventListener('click', handleSendMessage);

    // Отправка сообщения по Enter (с Shift+Enter для новой строки)
    document.getElementById('message-input').addEventListener('keydown', function(e) {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault(); // Предотвращаем перенос строки
            handleSendMessage(); // Отправляем сообщение
        }
    });

    document.getElementById('new-search-btn').addEventListener('click', handleNewSearch);
}

/**
 * Показ приветственного сообщения
 */
function showWelcomeMessage() {

    // Добавляем приветственное сообщение к локальной истории
    state.chat_history = [];

    // Отображаем всю историю
    Render.renderChatHistory(state.chat_history);
}

/**
 * Настройка обработчика polling
 */
function setupPollingHandler() {
    // Регистрируем callback для обработки обновлений
    window.ResearchPoller.onUpdate(async (research) => {
        // Проверяем, изменилось ли состояние
        if (research.id !== state.mr_id) {
            console.log('Получено обновление для другого исследования, игнорируем');
            return;
        }

        // Вычисляем хеш текущего состояния чата для сравнения
        const chatHash = JSON.stringify(research.chat_history);
        const currentChatHash = JSON.stringify(state.chat_history);
        
        // Проверяем, есть ли изменения
        const hasChatChanges = chatHash !== currentChatHash;
        const hasStatusChanges = research.state !== state.currentStatus;
        
        if (hasChatChanges || hasStatusChanges) {
            console.log('Обнаружены изменения в исследовании:', {
                hasChatChanges,
                hasStatusChanges,
                oldChatLength: state.chat_history.length,
                newChatLength: research.chat_history.length,
                oldStatus: state.currentStatus,
                newStatus: research.state
            });
            
            // Обновляем состояние
            state.chat_history = research.chat_history || [];
            state.currentStatus = research.state;
            
            // Обновляем интерфейс
            Render.renderChatHistory(state.chat_history);
            Render.renderStatus(research.state);
            
            // Автоматическая прокрутка к новым сообщениям
            const chatContainer = document.getElementById('chat-container');
            if (chatContainer) {
                chatContainer.scrollTop = chatContainer.scrollHeight;
            }
        }
        
        // Если поиск завершен, можем замедлить polling
        if (research.state === 'CHAT' && window.ResearchPoller.isPolling) {
            // После завершения поиска переключаемся на более редкий polling
            console.log('Поиск завершен, замедляем polling');
            window.ResearchPoller.startPolling(state.mr_id, 5000); // Раз в 5 секунд
        }
    });
}


/**
 * Обработка отправки сообщения (обновленная версия)
 */
async function handleSendMessage() {
    const input = document.getElementById('message-input');
    const messageText = input.value.trim();
    if (!messageText) return;

    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Отправка...';

    try {
        let research;
        
        if (state.mr_id === null) {
            // Создаем новое исследование
            research = await Api.startNewResearch(messageText);
            state.mr_id = research.id;
            
            // Запускаем polling для нового исследования
            window.ResearchPoller.startPolling(state.mr_id, 1000); // Быстрый polling при активном действии
        } else {
            // Отправляем в существующее
            research = await Api.sendChatMessage(state.mr_id, messageText);
            
            // Ускоряем polling после отправки сообщения
            window.ResearchPoller.startPolling(state.mr_id, 1000);
        }

        // Обновляем состояние из немедленного ответа
        state.chat_history = research.chat_history || [];
        state.currentStatus = research.state;

        // Обновляем интерфейс
        Render.renderChatHistory(state.chat_history);
        Render.renderStatus(research.state);

        input.value = '';
        
    } catch (error) {
        console.error('Ошибка:', error);
        alert('Ошибка соединения с сервером');
    } finally {
        sendBtn.disabled = false;
        sendBtn.textContent = 'Отправить';
    }
}


/**
 * Сброс состояния и начало нового исследования
 */
function handleNewSearch() {
    console.log('Начинаем новое исследование, сбрасываем состояние...');

    // 1. Останавливаем polling
    window.ResearchPoller.stopPolling();

    // 2. Сбрасываем глобальный объект состояния
    state.mr_id = null;
    state.chat_history = [];
    state.currentStatus = 'CHAT';
    state.lastChatUpdateId = 0;

    // 3. Очищаем интерфейс
    Render.clearChatContainer();
    Render.renderStatus('CHAT');

    // 4. Подготавливаем поле ввода
    const input = document.getElementById('message-input');
    input.value = '';
    input.focus();

    // 5. Опционально: можно вывести системное уведомление в консоль или интерфейс
    console.log('Приложение готово к новому поиску');
}

// Открытие истории
document.getElementById('history-btn').onclick = async () => {
    const list = await Api.getHistoryList();
    const container = document.getElementById('history-list');
    container.innerHTML = '';
    
    list.forEach(item => {
        const div = document.createElement('div');
        div.className = 'history-item';
        const date = new Date(item.updated_at).toLocaleDateString();
        
        div.innerHTML = `
            <div class="history-info">
                <span class="title">${item.title}</span>
                <span class="date">${date} | ${item.state}</span>
            </div>
            <button class="delete-btn" title="Удалить">&times;</button>
        `;

        // Клик по самому элементу — загружаем чат
        div.onclick = () => loadResearch(item.id);

        // Клик по кнопке удаления
        const delBtn = div.querySelector('.delete-btn');
        delBtn.onclick = async (e) => {
            e.stopPropagation(); // ВАЖНО: чтобы не сработал loadResearch
            
            if (confirm('Вы уверены, что хотите удалить этот поиск?')) {
                await Api.deleteResearch(item.id);
                
                // Если мы удаляем тот чат, который сейчас открыт — очищаем экран
                if (state.mr_id === item.id) {
                    handleNewSearch();
                }
                
                // Просто симулируем повторный клик на кнопку истории, чтобы обновить список
                document.getElementById('history-btn').click();
            }
        };

        container.appendChild(div);
    });
    
    document.getElementById('history-sidebar').classList.add('active');
    document.getElementById('overlay').style.display = 'block';
};

// Загрузка конкретного исследования
async function loadResearch(id) {
    try {
        const research = await Api.getMarketResearch(id);
        state.mr_id = research.id;
        state.chat_history = research.chat_history || [];
        state.currentStatus = research.state;

        Render.renderChatHistory(state.chat_history);
        Render.renderStatus(state.currentStatus);
        
        // Закрываем сайдбар
        document.getElementById('history-sidebar').classList.remove('active');
        document.getElementById('overlay').style.display = 'none';
        
        // Запускаем поллинг, если исследование в процессе
        window.ResearchPoller.startPolling(state.mr_id);
        
    } catch (e) {
        alert("Ошибка загрузки чата");
    }
}

// Закрытие
document.getElementById('close-history').onclick = document.getElementById('overlay').onclick = () => {
    document.getElementById('history-sidebar').classList.remove('active');
    document.getElementById('overlay').style.display = 'none';
};

// Инициализируем приложение при загрузке DOM
document.addEventListener('DOMContentLoaded', initApp);

// Экспортируем функции для отладки (опционально)
window.App = {
    state,
    handleSendMessage
};