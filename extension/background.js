const SERVER_URL = 'http://127.0.0.1:8001';

async function log(message, level = 'info') {
    try {
        await fetch(`${SERVER_URL}/api/log`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ source: 'background', message: String(message), level })
        });
    } catch (e) { }
}

log('Background v5.0 (Dynamic Limit) запущен.');

let activeTabs = {};

setInterval(async () => {
    try {
        const response = await fetch(`${SERVER_URL}/api/get_task`);
        if (!response.ok) return;
        const data = await response.json();

        if (data.task_id) {
            log(`🎯 Задача ID=${data.task_id} (Limit=${data.limit})`);
            // Передаем active_tab и limit
            performSearch(data.task_id, data.query, data.active_tab, data.limit);
        }
    } catch (e) { 
        console.error(e);
    }
}, 3000);

// Само-пинг
setInterval(() => { chrome.runtime.getPlatformInfo(() => {}); }, 20000);

function performSearch(taskId, query, makeActive, limit) {
    const encodedQuery = encodeURIComponent(query);
    const searchUrl = `https://www.avito.ru/rossiya?q=${encodedQuery}`; 
    
    const isActive = (makeActive === undefined) ? true : makeActive;
    
    log(`Открываю вкладку: ${searchUrl}`);
    
    chrome.tabs.create({ url: searchUrl, active: isActive }, (tab) => {
        // Сохраняем ID и Лимит
        activeTabs[tab.id] = { id: taskId, limit: limit };
    });
}

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (activeTabs[tabId] && changeInfo.status === 'complete') {
        const taskData = activeTabs[tabId];
        setTimeout(() => {
            log(`Вкладка ${tabId} готова.`);
            // Передаем taskId и limit в main.js
            chrome.tabs.sendMessage(tabId, { 
                action: 'start_parsing', 
                taskId: taskData.id,
                limit: taskData.limit 
            }).catch(() => {});
        }, 2000);
    }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.action === 'scrapedData') {
        const itemsCount = message.data.items ? message.data.items.length : 0;
        log(`📥 Финиш! Товаров: ${itemsCount}`);

        if (sender.tab) {
             const tabId = sender.tab.id;
             delete activeTabs[tabId];
             chrome.tabs.remove(tabId);
        }

        fetch(`${SERVER_URL}/api/submit_results`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(message.data)
        }).catch(err => log(`Ошибка отправки: ${err.message}`, 'error'));
    }

    if (message.action === 'log') {
        log(`(Content) ${message.message}`, message.level);
    }
});