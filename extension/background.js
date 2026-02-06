const SERVER_URL = 'http://127.0.0.1:8001';

function log(message, level = 'info') {
    const prefix = '[Background]';
    if (level === 'error') {
        console.error(prefix, message);
    } else {
        console.log(prefix, message);
    }
}

log('Background v5.0 (Dynamic Limit) запущен.');

let activeTabs = {};

setInterval(async () => {
    try {
        const response = await fetch(`${SERVER_URL}/api/get_task`);
        
        // 1. Если задач нет (204), просто выходим из функции без ошибки
        if (response.status === 204) {
            return; 
        }

        // 2. Если другой плохой статус (404, 500 и т.д.), выходим
        if (!response.ok) return;

        // 3. Теперь парсим, так как мы уверены, что там статус 200 и есть данные
        const data = await response.json();

        if (data && data.task_id) {
            log(`🎯 Задача ID=${data.task_id} (Limit=${data.limit})`);
            performSearch(data.task_id, data.query, data.active_tab, data.limit);
        }
    } catch (e) { 
        // Теперь здесь будут только реальные ошибки сети, а не SyntaxError
        console.error("Ошибка в цикле опроса задач:", e);
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

// Слушатель сообщений от контент-скриптов
chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    // Новое действие: закрытие вкладки после успеха
    if (message.action === 'closeCurrentTab') {
        if (sender.tab) {
            const tabId = sender.tab.id;
            log(`🎯 Задача завершена. Закрываю вкладку ${tabId}`);
            delete activeTabs[tabId];
            chrome.tabs.remove(tabId);
        }
    }

    // Это можно оставить для отладки в консоли фоновой страницы
    if (message.action === 'log') {
        log(`(Content) ${message.message}`, message.level);
    }
});