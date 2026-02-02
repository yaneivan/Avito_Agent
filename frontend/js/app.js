/**
 * Основной модуль приложения с управлением состоянием и поллингом
 */

// Объект состояния приложения
const state = {
    mr_id: null,              // ID текущего исследования
    messages: [],             // Локальная копия истории сообщений
    displayedMessageIds: new Set(), // Уже отображенные ID сообщений
    currentStatus: 'CHAT',    // Текущий статус (CHAT, SEARCHING_QUICK и т.д.)
    lastUpdate: 0,            // Timestamp последнего обновления
    pollingInterval: null,    // Интервал для поллинга
    pollingActive: false      // Активен ли поллинг
};

// Константы
const POLLING_INTERVAL_MS = 3000; // 3 секунды

/**
 * Инициализация приложения
 */
function initApp() {
    console.log('Инициализация приложения...');

    // Привязываем обработчики событий
    bindEventListeners();

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
    
    // Новый поиск
    document.getElementById('new-search-btn').addEventListener('click', startNewSearch);
}

/**
 * Показ приветственного сообщения
 */
function showWelcomeMessage() {
    const welcomeMsg = {
        role: 'assistant',
        content: 'Привет! Я - Avito Agent. Могу помочь вам с поиском товаров на Avito. Напишите, что вы ищете.',
        id: 'welcome-message' // Добавляем ID для приветственного сообщения
    };

    const messageElement = Render.renderMessage(welcomeMsg);
    if (messageElement) {
        Render.appendMessageToChat(messageElement);

        // Отмечаем приветственное сообщение как отображенное
        state.displayedMessageIds.add(welcomeMsg.id);
    }
}

/**
 * Обработка отправки сообщения
 */
async function handleSendMessage() {
    const input = document.getElementById('message-input');
    const messageText = input.value.trim();

    if (!messageText) {
        return; // Не отправляем пустые сообщения
    }

    // Блокируем кнопку отправки
    const sendBtn = document.getElementById('send-btn');
    sendBtn.disabled = true;
    sendBtn.textContent = 'Отправка...';

    try {
        // Сохраняем текущие отображенные ID
        const previousDisplayedIds = new Set(state.displayedMessageIds);

        // Используем унифицированный эндпоинт для обработки сообщения
        // Передаем ID исследования, если оно уже существует
        const research = await Api.unifiedChat(messageText, state.mr_id);

        // Обновляем состояние
        state.mr_id = research.id;
        state.currentStatus = research.state;

        // Находим новые сообщения, которые еще не были отображены
        const newMessages = research.chat_history.filter(msg => {
            // Проверяем, есть ли у сообщения ID и отображалось ли оно ранее
            return !msg.id || !previousDisplayedIds.has(msg.id);
        });

        // Обновляем сообщения
        state.messages = research.chat_history || [];

        // Обновляем интерфейс
        Render.renderStatus(research.state);

        // Добавляем сообщение пользователя в интерфейс (оптимистичный UI)
        const userMsg = {
            role: 'user',
            content: messageText
        };

        const userMsgElement = Render.renderMessage(userMsg);
        if (userMsgElement) {
            Render.appendMessageToChat(userMsgElement);
        }

        // Отображаем все новые сообщения, кроме текущего сообщения пользователя
        newMessages
            .filter(msg => !(msg.role === 'user' && msg.content === messageText))
            .forEach(msg => {
                const messageElement = Render.renderMessage(msg);
                if (messageElement) {
                    Render.appendMessageToChat(messageElement);

                    // Отмечаем сообщение как отображенное, если у него есть ID
                    if (msg.id) {
                        state.displayedMessageIds.add(msg.id);
                    }
                }
            });

        // Запускаем поллинг, если он еще не запущен
        if (!state.pollingActive) {
            startPolling();
        }

        // Очищаем поле ввода
        input.value = '';
    } catch (error) {
        console.error('Ошибка при отправке сообщения:', error);
        alert('Ошибка при отправке сообщения. Проверьте соединение с сервером.');
    } finally {
        // Разблокируем кнопку отправки
        sendBtn.disabled = false;
        sendBtn.textContent = 'Отправить';
    }
}

/**
 * Запуск нового поиска
 */
function startNewSearch() {
    // Очищаем состояние
    state.mr_id = null;
    state.messages = [];
    state.displayedMessageIds = new Set(); // Очищаем отображенные ID сообщений
    state.currentStatus = 'CHAT';

    // Очищаем чат
    Render.clearChatContainer();

    // Показываем приветственное сообщение снова
    showWelcomeMessage();

    // Обновляем статус
    Render.renderStatus('CHAT');

    // Останавливаем поллинг
    stopPolling();

    // Фокус на поле ввода
    document.getElementById('message-input').focus();
}

/**
 * Запуск поллинга состояния
 */
function startPolling() {
    if (state.pollingActive) {
        console.warn('Поллинг уже запущен');
        return;
    }
    
    console.log('Запуск поллинга...');
    state.pollingActive = true;
    
    // Запускаем интервал
    state.pollingInterval = setInterval(async () => {
        await pollState();
    }, POLLING_INTERVAL_MS);
}

/**
 * Остановка поллинга состояния
 */
function stopPolling() {
    if (state.pollingInterval) {
        clearInterval(state.pollingInterval);
        state.pollingInterval = null;
    }
    state.pollingActive = false;
    console.log('Поллинг остановлен');
}

/**
 * Цикл обновлений (поллинг)
 */
async function pollState() {
    if (!state.mr_id) {
        console.warn('Нет ID исследования для поллинга');
        stopPolling();
        return;
    }
    
    try {
        const research = await Api.getMarketResearch(state.mr_id);

        // Находим сообщения, которые еще не были отображены
        const newMessages = research.chat_history.filter(msg => {
            // Проверяем, есть ли у сообщения ID и отображалось ли оно ранее
            return !msg.id || !state.displayedMessageIds.has(msg.id);
        });

        // Добавляем новые сообщения в интерфейс
        newMessages.forEach(msg => {
            const messageElement = Render.renderMessage(msg);
            if (messageElement) {
                Render.appendMessageToChat(messageElement);

                // Отмечаем сообщение как отображенное, если у него есть ID
                if (msg.id) {
                    state.displayedMessageIds.add(msg.id);
                }
            }
        });

        // Обновляем локальное состояние
        state.messages = [...research.chat_history];

        // Проверяем, изменился ли статус
        if (research.state !== state.currentStatus) {
            state.currentStatus = research.state;
            Render.renderStatus(research.state);

            // Если статус "поиск", блокируем кнопку отправки
            const sendBtn = document.getElementById('send-btn');
            if (research.state === 'SEARCHING_QUICK' ||
                research.state === 'PLANNING_DEEP_RESEARCH' ||
                research.state === 'DEEP_RESEARCH') {
                sendBtn.disabled = true;
                sendBtn.textContent = 'Агент ищет...';
            } else {
                sendBtn.disabled = false;
                sendBtn.textContent = 'Отправить';
            }
        }

        // Обновляем время последнего обновления
        state.lastUpdate = Date.now();
    } catch (error) {
        console.error('Ошибка при поллинге состояния:', error);
        
        // Если ошибка 404 (исследование не найдено), останавливаем поллинг
        if (error.message.includes('404')) {
            console.log('Исследование не найдено, останавливаем поллинг');
            stopPolling();
        }
    }
}

// Инициализируем приложение при загрузке DOM
document.addEventListener('DOMContentLoaded', initApp);

// Экспортируем функции для отладки (опционально)
window.App = {
    state,
    startPolling,
    stopPolling,
    pollState
};