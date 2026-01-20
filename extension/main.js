// --- Глобальное состояние ---
const collectedItems = new Map();

// --- Слушатель ---
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'start_parsing') {
        // Определяем лимит: либо то, что прислал сервер, либо дефолт из конфига
        const limit = request.limit || CONFIG.TARGET_COUNT;
        
        remoteLog(`🔔 Задача ID=${request.taskId}. Старт. Цель: ${limit} шт.`);
        runScraper(request.taskId, limit);
    }
});

// --- Сценарий ---
async function runScraper(taskId, targetCount) {
    try {
        await randomDelay(CONFIG.START_DELAY.MIN, CONFIG.START_DELAY.MAX);
        let emptyScrolls = 0;

        // Используем переданный targetCount
        while (collectedItems.size < targetCount) {
            
            remoteLog(`⬇️ Листаю... (${collectedItems.size}/${targetCount})`);
            
            // Используем Actions из actions.js
            await Actions.humanScroll(window.innerHeight * 0.85);
            
            await randomDelay(CONFIG.SCROLL_DELAY.MIN, CONFIG.SCROLL_DELAY.MAX);

            // Используем processVisibleItems (функция ниже)
            const foundNew = await processVisibleItems(targetCount);
            
            if (!foundNew) {
                emptyScrolls++;
                remoteLog(`⚠️ Новых нет (${emptyScrolls}/${CONFIG.MAX_EMPTY_SCROLLS})`);
                
                if (emptyScrolls > 2) {
                    window.scrollBy(0, -300);
                    await randomDelay(500, 800);
                    window.scrollBy(0, 300);
                    await randomDelay(1000, 1500);
                }
            } else {
                emptyScrolls = 0;
            }

            const reachedBottom = (window.innerHeight + window.scrollY) >= document.body.scrollHeight - 50;
            if (reachedBottom) {
                remoteLog('🛑 Достигнут конец страницы.');
                break;
            }
            
            if (emptyScrolls >= CONFIG.MAX_EMPTY_SCROLLS) {
                remoteLog('🛑 Лимит попыток исчерпан.');
                break;
            }
        }

        remoteLog(`✅ Финиш. Всего: ${collectedItems.size}.`);
        sendData(taskId, Array.from(collectedItems.values()));

    } catch (e) {
        remoteLog(`Fatal Error: ${e.message}`, 'error');
        sendData(taskId, Array.from(collectedItems.values()));
    }
}

async function processVisibleItems(targetCount) {
    // Используем AvitoParser из parsers.js
    const cards = AvitoParser.findItems(); 
    let foundNew = false;

    for (const card of cards) {
        // Проверка лимита
        if (collectedItems.size >= targetCount) break;

        const rect = card.getBoundingClientRect();
        if (rect.top > window.innerHeight + 300) continue; 
        if (rect.bottom < -300) continue; 

        // Легкая проверка URL перед тяжелым парсингом
        const urlElem = card.querySelector('[itemprop="url"]');
        const url = urlElem ? urlElem.href : null;

        if (!url || collectedItems.has(url)) continue;

        // Полный парсинг карточки
        const itemData = await AvitoParser.extractData(card);
        
        if (itemData) {
            highlightElement(card, "green"); // из utils.js
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