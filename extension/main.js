// --- Глобальное состояние ---
let collectedItems = new Map();

// --- Слушатель ---
chrome.runtime.onMessage.addListener(async (request, sender, sendResponse) => {
    if (request.action === 'start_parsing') {
        const taskId = request.taskId;
        const limit = request.limit || CONFIG.TARGET_COUNT;

        // 1. Пытаемся восстановить данные из хранилища (если мы перешли со страницы 1 на страницу 2 и т.д.)
        const storageKey = `avito_pending_task_${taskId}`;
        try {
            const result = await chrome.storage.local.get(storageKey);
            if (result[storageKey]) {
                const prevItems = result[storageKey];
                prevItems.forEach(item => collectedItems.set(item.url, item));
                remoteLog(`🔄 Восстановлено из памяти: ${collectedItems.size} шт.`);
            }
        } catch (e) {
            remoteLog("Ошибка восстановления данных из storage", "error");
        }
        
        remoteLog(`🔔 Задача ID=${taskId}. Старт. Цель: ${limit} шт.`);
        runScraper(taskId, limit);
    }
});

// --- Сценарий ---
async function runScraper(taskId, targetCount) {
    const storageKey = `avito_pending_task_${taskId}`;

    try {
        await randomDelay(CONFIG.START_DELAY.MIN, CONFIG.START_DELAY.MAX);
        let emptyScrolls = 0;

        while (collectedItems.size < targetCount) {
            
            remoteLog(`⬇️ Листаю... (${collectedItems.size}/${targetCount})`);
            
            // Используем Actions из actions.js
            await Actions.humanScroll(window.innerHeight * 0.85);
            
            await randomDelay(CONFIG.SCROLL_DELAY.MIN, CONFIG.SCROLL_DELAY.MAX);

            // Собираем товары на текущем экране
            const foundNew = await processVisibleItems(targetCount);
            
            if (!foundNew) {
                emptyScrolls++;
                remoteLog(`⚠️ Новых нет (${emptyScrolls}/${CONFIG.MAX_EMPTY_SCROLLS})`);
                
                // Если "застряли", пробуем дернуть страницу
                if (emptyScrolls > 2) {
                    window.scrollBy(0, -300);
                    await randomDelay(500, 800);
                    window.scrollBy(0, 300);
                    await randomDelay(1000, 1500);
                }
            } else {
                emptyScrolls = 0;
            }

            // Проверка: достигли ли низа страницы?
            const reachedBottom = (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 200;
            
            if (reachedBottom) {
                // Если лимит еще не достигнут, ищем кнопку пагинации
                if (collectedItems.size < targetCount) {
                    const nextLink = document.querySelector(CONFIG.SELECTORS.PAGINATION_NEXT);
                    
                    if (nextLink && nextLink.href) {
                        remoteLog(`➡️ Лимит не достигнут (${collectedItems.size}/${targetCount}). Перехожу на следующую страницу...`);
                        
                        // СОХРАНЯЕМ ПРОГРЕСС перед уходом со страницы
                        await chrome.storage.local.set({ [storageKey]: Array.from(collectedItems.values()) });
                        
                        // Переходим по ссылке
                        window.location.href = nextLink.href;
                        return; // Останавливаем выполнение скрипта, страница перезагрузится
                    } else {
                        remoteLog('🛑 Больше страниц нет. Завершаю с тем, что есть.');
                        break;
                    }
                } else {
                    remoteLog('🛑 Лимит достигнут на текущей странице.');
                    break;
                }
            }
            
            if (emptyScrolls >= CONFIG.MAX_EMPTY_SCROLLS) {
                remoteLog('🛑 Лимит попыток (пустой скролл) исчерпан.');
                break;
            }
        }

        // Если мы здесь — значит либо набрали лимит, либо страницы кончились
        remoteLog(`✅ Финиш. Всего собрано: ${collectedItems.size}.`);
        
        // Очищаем временную память задачи, так как она успешно завершена
        await chrome.storage.local.remove(storageKey);

        sendData(taskId, Array.from(collectedItems.values()));

    } catch (e) {
        remoteLog(`Fatal Error: ${e.message}`, 'error');
        // В случае ошибки пытаемся отправить хоть что-то
        sendData(taskId, Array.from(collectedItems.values()));
    }
}

async function processVisibleItems(targetCount) {
    const cards = AvitoParser.findItems(); 
    let foundNew = false;

    for (const card of cards) {
        if (collectedItems.size >= targetCount) break;

        const rect = card.getBoundingClientRect();
        // Парсим только то, что близко к области видимости
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

function sendData(taskId, items) {
    chrome.runtime.sendMessage({
        action: 'scrapedData',
        data: { task_id: taskId, items: items }
    });
}