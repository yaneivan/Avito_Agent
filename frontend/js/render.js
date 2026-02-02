/**
 * Модуль рендеринга для отображения сообщений
 */

/**
 * Рендеринг сообщения
 * @param {Object} msg - Объект сообщения
 * @param {string} msg.role - Роль отправителя ('user' или 'assistant')
 * @param {string} msg.content - Текст сообщения
 * @returns {HTMLElement} - DOM элемент сообщения
 */
function renderMessage(msg) {
    // Выбираем шаблон в зависимости от роли
    const templateId = msg.role === 'user' ? '#msg-user-tpl' : '#msg-bot-tpl';
    const template = document.querySelector(templateId);

    if (!template) {
        console.error(`Шаблон ${templateId} не найден`);
        return null;
    }

    const clone = template.content.cloneNode(true);
    const messageElement = clone.querySelector('.message');
    const contentElement = clone.querySelector('.message-content');

    // Обработка и отображение текста сообщения с поддержкой Markdown
    if (msg.content) {
        // Используем marked.js для преобразования Markdown в HTML
        const parsedHtml = window.marked.parse(msg.content);
        contentElement.innerHTML = parsedHtml;
    }

    return messageElement;
}

/**
 * Очистка контейнера чата
 */
function clearChatContainer() {
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer) {
        chatContainer.innerHTML = '';
    }
}

/**
 * Отображение всей истории чата
 * @param {Array} chatHistory - Массив сообщений
 */
function renderChatHistory(chatHistory) {
    const chatContainer = document.getElementById('chat-container');
    if (!chatContainer) return;

    // Очищаем контейнер
    chatContainer.innerHTML = '';

    // Добавляем все сообщения
    chatHistory.forEach(msg => {
        const messageElement = renderMessage(msg);
        if (messageElement) {
            chatContainer.appendChild(messageElement);
        }
    });

    // Прокручиваем вниз
    chatContainer.scrollTop = chatContainer.scrollHeight;
}

/**
 * Рендеринг статуса
 * @param {string} status - Текущий статус
 */
function renderStatus(status) {
    const statusIndicator = document.getElementById('status-indicator');
    if (!statusIndicator) return;

    // Удаляем предыдущие классы статуса
    statusIndicator.classList.remove('status-ready', 'status-searching');

    // Устанавливаем текст и класс в зависимости от статуса
    switch (status) {
        case 'CHAT':
            statusIndicator.textContent = 'Готов';
            statusIndicator.classList.add('status-ready');
            break;
        case 'SEARCHING_QUICK':
        case 'PLANNING_DEEP_RESEARCH':
        case 'DEEP_RESEARCH':
            statusIndicator.textContent = 'Поиск...';
            statusIndicator.classList.add('status-searching');
            break;
        default:
            statusIndicator.textContent = status || 'Готов';
            statusIndicator.classList.add('status-ready');
    }
}



// Экспортируем функции для использования в других модулях
window.Render = {
    renderMessage,
    renderChatHistory,
    clearChatContainer,
    renderStatus
};