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
    console.log("Rendering message:", msg); // ПОСМОТРИ В КОНСОЛЬ БРАУЗЕРА

    const templateId = msg.role === 'user' ? '#msg-user-tpl' : '#msg-bot-tpl';
    const template = document.querySelector(templateId);
    const clone = template.content.cloneNode(true);
    const messageElement = clone.querySelector('.message');
    const contentElement = clone.querySelector('.message-content');

    // Рендерим текст (Markdown)
    if (msg.content) {
        contentElement.innerHTML = window.marked.parse(msg.content);
    }

    // --- НОВОЕ: Рендерим плитки лотов ---
    if (msg.role === 'assistant' && msg.items && msg.items.length > 0) {
        const lotsContainer = clone.querySelector('.lots-container');
        const lotTemplate = document.querySelector('#lot-card-tpl');

        msg.items.forEach(item => {
            const lotClone = lotTemplate.content.cloneNode(true);
            
            lotClone.querySelector('.lot-title').textContent = item.title;
            lotClone.querySelector('.lot-price').textContent = Utils.formatPrice(item.price);
            lotClone.querySelector('.lot-link').href = item.url;
            
            // Обработка картинки (преобразуем системный путь в URL)
            console.log('Processing item:', item); // Лог для отладки
            if (item.image_path) {
                console.log('Found image_path:', item.image_path); // Лог для отладки

                // Преобразуем системный путь к изображению в URL, обслуживаемый FastAPI
                let imgUrl = item.image_path;

                // Если путь начинается с './data/images/', заменяем на '/images/' для FastAPI
                if (imgUrl.startsWith('./data/images/')) {
                    imgUrl = imgUrl.replace('./data/images/', '/images/');
                }
                // Если путь начинается с 'data/images/', тоже заменяем на '/images/'
                else if (imgUrl.startsWith('data/images/')) {
                    imgUrl = imgUrl.replace('data/images/', '/images/');
                }
                // Если путь содержит 'data/images/' в любом месте, заменяем на '/images/'
                else if (imgUrl.includes('data/images/')) {
                    imgUrl = imgUrl.replace(/.*?data\/images\//, '/images/');
                }
                // Если путь уже является абсолютным URL, оставляем как есть
                else if (!imgUrl.startsWith('/')) {
                    // Если путь не начинается с '/', добавляем '/images/' в начало
                    imgUrl = '/images/' + imgUrl;
                }

                console.log('Converted imgUrl:', imgUrl); // Лог для отладки
                lotClone.querySelector('.lot-image').src = imgUrl;
            } else {
                console.log('No image_path found for item'); // Лог для отладки
            }

            lotsContainer.appendChild(lotClone);
        });
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

    // 1. Очищаем ВСЕ возможные классы статусов перед добавлением нового
    statusIndicator.classList.remove('status-ready', 'status-searching');

    // 2. Логика выбора текста и класса
    switch (status) {
        case 'CHAT':
            statusIndicator.textContent = 'Готов';
            statusIndicator.classList.add('status-ready');
            break;
            
        case 'PLANNING_DEEP_RESEARCH':
            statusIndicator.textContent = 'Жду подтверждения';
            statusIndicator.classList.add('status-ready'); // Или отдельный цвет
            break;

        case 'SEARCHING_QUICK':
        case 'DEEP_RESEARCH':
            statusIndicator.textContent = 'Ищу на Avito...';
            statusIndicator.classList.add('status-searching');
            break;

        default:
            statusIndicator.textContent = status;
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