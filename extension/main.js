// --- Глобальное состояние ---
let collectedItems = new Map();
let isSubmitting = false;   // Флаг для предотвращения двойной отправки
let scraperRunning = true;  // Флаг для мгновенной остановки циклов

// Константа сервера (можно вынести в config.js)
const API_URL = 'http://127.0.0.1:8001/api';

// --- Слушатель сообщений ---
chrome.runtime.onMessage.addListener(async (request, sender, sendResponse) => {
    if (request.action === 'start_parsing') {
        const taskId = request.taskId;
        const limit = request.limit || CONFIG.TARGET_COUNT;

        // Восстановление данных из памяти
        const storageKey = `avito_pending_task_${taskId}`;
        try {
            const result = await chrome.storage.local.get(storageKey);
            if (result[storageKey]) {
                const prevItems = result[storageKey];
                prevItems.forEach(item => collectedItems.set(item.url, item));
                remoteLog(`🔄 Восстановлено: ${collectedItems.size} шт.`);
            }
        } catch (e) {
            remoteLog("Ошибка чтения storage", "error");
        }
        
        remoteLog(`🔔 Задача ID=${taskId}. Цель: ${limit} шт.`);
        runScraper(taskId, limit);
    }
});

// --- Основной сценарий ---
async function runScraper(taskId, targetCount) {
    const storageKey = `avito_pending_task_${taskId}`;

    try {
        await randomDelay(CONFIG.START_DELAY.MIN, CONFIG.START_DELAY.MAX);
        let emptyScrolls = 0;

        while (scraperRunning && collectedItems.size < targetCount) {
            remoteLog(`⬇️ Листаю... (${collectedItems.size}/${targetCount})`);
            await Actions.humanScroll(window.innerHeight * 0.85);
            await randomDelay(CONFIG.SCROLL_DELAY.MIN, CONFIG.SCROLL_DELAY.MAX);

            // ПЕРЕДАЕМ taskId сюда 👇
            const foundNew = await processVisibleItems(targetCount, taskId);
            
            if (!foundNew) {
                emptyScrolls++;
                if (emptyScrolls > 2) {
                    window.scrollBy(0, -300);
                    await randomDelay(500, 800);
                    window.scrollBy(0, 300);
                }
            } else {
                emptyScrolls = 0;
            }

            const reachedBottom = (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 200;
            if (reachedBottom && scraperRunning) {
                if (collectedItems.size < targetCount) {
                    const nextLink = document.querySelector(CONFIG.SELECTORS.PAGINATION_NEXT);
                    if (nextLink && nextLink.href) {
                        remoteLog(`➡️ Переход на следующую страницу...`);
                        await chrome.storage.local.set({ [storageKey]: Array.from(collectedItems.values()) });
                        window.location.href = nextLink.href;
                        return; 
                    }
                }
                break; 
            }
            if (emptyScrolls >= CONFIG.MAX_EMPTY_SCROLLS) break;
        }

        if (scraperRunning) {
            await finishAndSendData(taskId);
        }
    } catch (e) {
        remoteLog(`Fatal Error: ${e.message}`, 'error');
        await finishAndSendData(taskId);
    }
}

/**
 * Финальная отправка данных на сервер
 */
async function finishAndSendData(taskId) {
    if (isSubmitting || !taskId) return; 
    if (isSubmitting) return; // Защита от двойного вызова
    
    isSubmitting = true;
    scraperRunning = false; // Мгновенно останавливаем любые скроллы

    const storageKey = `avito_pending_task_${taskId}`;
    const payload = {
        task_id: taskId,
        items: Array.from(collectedItems.values())
    };

    remoteLog(`🚀 Отправка ${payload.items.length} лотов на сервер...`);

    try {
        const response = await fetch(`${API_URL}/submit_results`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (response.ok) {
            remoteLog(`✅ Бэкенд принял данные. Очистка памяти.`);
            
            // 1. Очищаем хранилище текущей задачи
            await chrome.storage.local.remove(storageKey);
            
            // 2. Сигнализируем background.js закрыть вкладку
            chrome.runtime.sendMessage({ action: 'closeCurrentTab' });
        } else {
            throw new Error(`Server status: ${response.status}`);
        }

    } catch (e) {
        remoteLog(`❌ Ошибка отправки: ${e.message}. Повтор через 10 сек...`, 'error');
        isSubmitting = false; // Сбрасываем флаг для возможности повтора
        
        // Согласно ТЗ: Ждем 10 секунд и пробуем снова
        setTimeout(() => {
            finishAndSendData(taskId);
        }, 10000);
    }
}

async function processVisibleItems(targetCount, taskId) { // Добавили taskId
    if (!scraperRunning) return false;

    const cards = AvitoParser.findItems(); 
    let foundNew = false;

    for (const card of cards) {
        if (collectedItems.size >= targetCount) {
            if (scraperRunning) {
                remoteLog("🎯 Лимит достигнут!");
                await finishAndSendData(taskId); // ТЕПЕРЬ ПЕРЕДАЕМ taskId, а не null
            }
            break;
        }

        const rect = card.getBoundingClientRect();
        if (rect.top > window.innerHeight + 500) continue; 
        if (rect.bottom < -500) continue; 

        const urlElem = card.querySelector('[itemprop="url"]');
        const url = urlElem ? urlElem.href : null;

        if (!url || collectedItems.has(url)) continue;

        const itemData = await AvitoParser.extractData(card);
        if (itemData) {
            highlightElement(card, "green"); 
            collectedItems.set(itemData.url, itemData);
            foundNew = true;
            await randomDelay(CONFIG.ITEM_DELAY.MIN, CONFIG.ITEM_DELAY.MAX);
        }
    }
    return foundNew;
}