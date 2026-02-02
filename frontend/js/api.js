/**
 * API модуль для взаимодействия с сервером
 */

// Базовый URL API
const API_BASE_URL = '/api';

/**
 * Создание нового исследования рынка
 * @param {string} query - Поисковый запрос
 * @returns {Promise<Object>} - Объект исследования
 */
async function createMarketResearch(query) {
    try {
        const response = await fetch(`${API_BASE_URL}/market_research`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                initial_query: query
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
 * Отправка сообщения в чат
 * @param {number} id - ID исследования
 * @param {string} text - Текст сообщения
 * @returns {Promise<Object>} - Обновленное состояние исследования
 */
async function sendMessage(id, text) {
    try {
        const response = await fetch(`${API_BASE_URL}/chat/${id}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                message: text
            })
        });

        if (!response.ok) {
            throw new Error(`Ошибка отправки сообщения: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Ошибка при отправке сообщения:', error);
        throw error;
    }
}

/**
 * Унифицированный чат-эндпоинт (фасад)
 * @param {string} message - Текст сообщения
 * @param {number|null} mrId - ID существующего исследования (опционально)
 * @returns {Promise<Object>} - Обновленное состояние исследования
 */
async function unifiedChat(message, mrId = null) {
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
            throw new Error(`Ошибка чата: ${response.status}`);
        }

        return await response.json();
    } catch (error) {
        console.error('Ошибка при чате:', error);
        alert('Ошибка соединения с сервером. Проверьте, запущен ли backend.');
        throw error;
    }
}

// Экспортируем функции для использования в других модулях
window.Api = {
    createMarketResearch,
    getMarketResearch,
    sendMessage,
    unifiedChat
};