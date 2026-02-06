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
    console.log("Rendering message:", msg);

    const templateId = msg.role === 'user' ? '#msg-user-tpl' : '#msg-bot-tpl';
    const template = document.querySelector(templateId);
    const clone = template.content.cloneNode(true);
    const messageElement = clone.querySelector('.message');
    const contentElement = clone.querySelector('.message-content');

    // 1. Рендерим текст (Markdown)
    if (msg.content) {
        contentElement.innerHTML = window.marked.parse(msg.content);
    }

    // --- ДОБАВЛЕНО: Кнопка таблицы сравнения ---
    // Если это ответ бота и в нем есть ID задачи поиска
    if (msg.role === 'assistant' && msg.task_id) {
        const tableBtn = document.createElement('button');
        tableBtn.className = 'view-table-btn';
        tableBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-right: 8px; vertical-align: middle;">
                <path d="M3 3h18v18H3zM3 9h18M3 15h18M9 3v18M15 3v18"/>
            </svg>
            Открыть таблицу сравнения
        `;
        tableBtn.onclick = () => {
            window.open(`/table.html?task_id=${msg.task_id}`, '_blank');
        };
        // Добавляем кнопку в конец текстового контента
        contentElement.appendChild(tableBtn);
    }

    // 2. Рендерим плитки лотов (уже было, сохраняем)
    if (msg.role === 'assistant' && msg.items && msg.items.length > 0) {
        const lotsContainer = clone.querySelector('.lots-container');
        const lotTemplate = document.querySelector('#lot-card-tpl');

        msg.items.forEach(item => {
            const lotClone = lotTemplate.content.cloneNode(true);
            
            lotClone.querySelector('.lot-title').textContent = item.title;
            lotClone.querySelector('.lot-price').textContent = Utils.formatPrice(item.price);
            lotClone.querySelector('.lot-link').href = item.url;
            
            // Обработка картинки
            if (item.image_path) {
                let imgUrl = item.image_path;

                // Унификация путей для FastAPI
                if (imgUrl.startsWith('./data/images/')) {
                    imgUrl = imgUrl.replace('./data/images/', '/images/');
                } else if (imgUrl.startsWith('data/images/')) {
                    imgUrl = imgUrl.replace('data/images/', '/images/');
                } else if (imgUrl.includes('data/images/')) {
                    imgUrl = imgUrl.replace(/.*?data\/images\//, '/images/');
                } else if (!imgUrl.startsWith('/') && !imgUrl.startsWith('http')) {
                    imgUrl = '/images/' + imgUrl;
                }

                lotClone.querySelector('.lot-image').src = imgUrl;
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