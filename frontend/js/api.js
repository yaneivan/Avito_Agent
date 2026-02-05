/**
 * API модуль для взаимодействия с сервером
 */

// Базовый URL API
const API_BASE_URL = '/api';

/**
 * Создание нового исследования
 * @param {string} initialQuery - Начальный запрос
 * @returns {Promise<Object>} - Созданное исследование
 */
async function createMarketResearch(initialQuery) {
    try {
        const response = await fetch(`${API_BASE_URL}/market_research`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                initial_query: initialQuery
            })
        });

        if (!response.ok) {
            throw new Error(`Ошибка создания исследования: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Ошибка при создании исследования:', error);
        alert('Ошибка соединения с сервером. Проверьте, запущен ли backend.');
        throw error;
    }
}

/**
 * Отправка сообщения в существующее исследование
 * @param {string} message - Текст сообщения
 * @param {number} mrId - ID существующего исследования
 * @returns {Promise<Object>} - Обновленное состояние исследования
 */
async function sendMessageToResearch(message, mrId) {
    try {
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: message,
                mr_id: mrId
            })
        });

        if (!response.ok) {
            throw new Error(`Ошибка отправки сообщения: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Ошибка при отправке сообщения:', error);
        alert('Ошибка соединения с сервером. Проверьте, запущен ли backend.');
        throw error;
    }
}


/**
 * Создание нового исследования
 */
async function startNewResearch(message) {
    const response = await fetch(`${API_BASE_URL}/market_research`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({initial_query: message})
    });
    if (!response.ok) throw new Error(`Ошибка создания: ${response.status}`);
    return await response.json();
}

/**
 * Отправка сообщения в существующее исследование
 */
async function sendChatMessage(mrId, message) {
    const response = await fetch(`${API_BASE_URL}/chat/${mrId}`, {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: message})
    });
    if (!response.ok) throw new Error(`Ошибка отправки: ${response.status}`);
    return await response.json();
}

// Экспорт (оставить getMarketResearch)
window.Api = {
    startNewResearch,
    sendChatMessage,
    getMarketResearch
};

/**
 * Получение информации о текущем исследовании
 * @param {number} id - ID исследования
 * @returns {Promise<Object>} - Объект исследования
 */
async function getMarketResearch(id) {
    try {
        const response = await fetch(`${API_BASE_URL}/market_research/${id}`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        if (!response.ok) {
            if (response.status === 404) {
                throw new Error('Исследование не найдено');
            }
            throw new Error(`Ошибка получения исследования: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Ошибка при получении исследования:', error);
        throw error;
    }
}

/**
 * Модуль для polling состояния исследования
 */
class ResearchPoller {
    constructor() {
        this.pollingInterval = null;
        this.isPolling = false;
        this.pollingCallbacks = [];
    }

    /**
     * Начать polling исследования
     * @param {number} mrId - ID исследования
     * @param {number} interval - Интервал в миллисекундах (по умолчанию 2 секунды)
     */
    startPolling(mrId, interval = 2000) {
        // Останавливаем предыдущий polling, если был
        this.stopPolling();
        
        console.log(`Начинаем polling исследования ${mrId} с интервалом ${interval}мс`);
        
        this.isPolling = true;
        this.pollingInterval = setInterval(async () => {
            try {
                const research = await getMarketResearch(mrId);
                
                // Вызываем все зарегистрированные коллбэки
                this.pollingCallbacks.forEach(callback => {
                    callback(research);
                });
                
            } catch (error) {
                console.error('Ошибка при polling:', error);
            }
        }, interval);
    }

    /**
     * Остановить polling
     */
    stopPolling() {
        if (this.pollingInterval) {
            console.log('Останавливаем polling');
            clearInterval(this.pollingInterval);
            this.pollingInterval = null;
            this.isPolling = false;
        }
    }

    /**
     * Зарегистрировать коллбэк для обновлений
     * @param {Function} callback - Функция, которая будет вызвана при каждом обновлении
     */
    onUpdate(callback) {
        this.pollingCallbacks.push(callback);
    }

    /**
     * Удалить коллбэк
     * @param {Function} callback - Функция для удаления
     */
    removeCallback(callback) {
        const index = this.pollingCallbacks.indexOf(callback);
        if (index > -1) {
            this.pollingCallbacks.splice(index, 1);
        }
    }
}

// Создаем глобальный экземпляр
window.ResearchPoller = new ResearchPoller();

// Экспортируем функции для использования в других модулях
window.Api = {
    startNewResearch,
    sendChatMessage,
    getMarketResearch
};