/**
 * Модуль рендеринга для отображения сообщений и карточек товаров
 */

/**
 * Рендеринг сообщения
 * @param {Object} msg - Объект сообщения
 * @param {string} msg.role - Роль отправителя ('user' или 'assistant')
 * @param {string} msg.content - Текст сообщения
 * @param {Array} msg.items - Массив товаров (если есть)
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
    
    // Если это сообщение бота и есть товары, отображаем их
    if (msg.role === 'assistant' && msg.items && Array.isArray(msg.items)) {
        const lotsContainer = clone.querySelector('.lots-container');
        if (lotsContainer) {
            msg.items.forEach(item => {
                const lotCard = renderLotCard(item);
                if (lotCard) {
                    lotsContainer.appendChild(lotCard);
                }
            });
        }
    }
    
    return messageElement;
}

/**
 * Рендеринг карточки товара
 * @param {Object} item - Объект товара
 * @param {string} item.title - Название товара
 * @param {string} item.price - Цена товара
 * @param {string} item.url - URL товара на Avito
 * @param {string} item.image_base64 - Изображение в base64 (опционально)
 * @returns {HTMLElement} - DOM элемент карточки товара
 */
function renderLotCard(item) {
    const template = document.querySelector('#lot-card-tpl');
    
    if (!template) {
        console.error('Шаблон #lot-card-tpl не найден');
        return null;
    }
    
    const clone = template.content.cloneNode(true);
    const cardElement = clone.querySelector('.lot-card');
    const imageElement = clone.querySelector('.lot-image');
    const titleElement = clone.querySelector('.lot-title');
    const priceElement = clone.querySelector('.lot-price');
    const linkElement = clone.querySelector('.lot-link');
    
    // Устанавливаем данные
    titleElement.textContent = item.title || 'Без названия';
    priceElement.textContent = Utils.formatPrice(item.price) || 'Цена не указана';
    linkElement.href = item.url || '#';
    linkElement.textContent = 'Смотреть на Avito';
    
    // Устанавливаем изображение, если оно есть
    if (item.image_base64) {
        // Проверяем, начинается ли строка с префикса data:image
        const imageData = item.image_base64.startsWith('data:image') 
            ? item.image_base64 
            : `data:image/jpeg;base64,${item.image_base64}`;
        imageElement.src = imageData;
    } else {
        // Если изображения нет, скрываем элемент
        imageElement.style.display = 'none';
    }
    
    return cardElement;
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
 * Добавление сообщения в контейнер чата
 * @param {HTMLElement} messageElement - DOM элемент сообщения
 */
function appendMessageToChat(messageElement) {
    const chatContainer = document.getElementById('chat-container');
    if (chatContainer && messageElement) {
        chatContainer.appendChild(messageElement);
        // Прокручиваем вниз
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
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

/**
 * Рендеринг визуальных вложений (заглушка для будущего использования)
 * @param {Array} attachments - Массив визуальных вложений
 */
function renderVisualAttachments(attachments) {
    // Пока пустая функция, зарезервирована для будущего использования
    console.log('Визуальные вложения:', attachments);
}

// Экспортируем функции для использования в других модулях
window.Render = {
    renderMessage,
    renderLotCard,
    clearChatContainer,
    appendMessageToChat,
    renderStatus,
    renderVisualAttachments
};