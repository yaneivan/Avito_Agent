/**
 * Вспомогательные утилиты для форматирования данных
 */

/**
 * Форматирование цены
 * @param {string|number} price - Цена
 * @returns {string} - Отформатированная цена
 */
function formatPrice(price) {
    if (!price) return 'Цена не указана';
    
    // Преобразуем в строку, если число
    const priceStr = String(price);
    
    // Убираем все нецифровые символы кроме пробелов
    const cleanedPrice = priceStr.replace(/[^\d\s]/g, '');
    
    // Добавляем пробелы как разделители тысяч
    return cleanedPrice.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

/**
 * Форматирование даты
 * @param {Date|string} date - Дата
 * @returns {string} - Отформатированная дата
 */
function formatDate(date) {
    const d = typeof date === 'string' ? new Date(date) : date;
    
    if (!(d instanceof Date) || isNaN(d.getTime())) {
        return 'Дата не указана';
    }
    
    return d.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Экранирование HTML
 * @param {string} text - Текст для экранирования
 * @returns {string} - Экранированный текст
 */
function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Проверка, является ли строка URL
 * @param {string} str - Строка для проверки
 * @returns {boolean} - Является ли строка URL
 */
function isUrl(str) {
    try {
        new URL(str);
        return true;
    } catch (_) {
        return false;
    }
}

/**
 * Генерация уникального ID
 * @returns {string} - Уникальный ID
 */
function generateId() {
    return Date.now().toString(36) + Math.random().toString(36).substr(2, 5);
}

// Экспортируем функции для использования в других модулях
window.Utils = {
    formatPrice,
    formatDate,
    escapeHtml,
    isUrl,
    generateId
};