const AvitoParser = {
    /**
     * Пытается найти контейнеры товаров на странице.
     */
    findItems: function() {
        const items = document.querySelectorAll(CONFIG.SELECTORS.ITEM_CARD);
        return Array.from(items);
    },

    /**
     * Извлекает данные из одной DOM-ноды карточки.
     */
    extractData: async function(card) {
        try {
            const urlElem = card.querySelector('[itemprop="url"]');
            const url = urlElem ? urlElem.href : null;

            if (!url) return null;

            // --- Текст Заголовка ---
            const title = card.querySelector('[itemprop="name"]')?.innerText || "Без названия";
            
            // --- Цена ---
            let price = "0";
            const priceMeta = card.querySelector('[itemprop="price"]');
            if (priceMeta) price = priceMeta.getAttribute('content');
            else {
                const textPrice = card.innerText.match(/(\d[\d\s]*)\s?₽/);
                if (textPrice) price = textPrice[1].replace(/\s/g, '');
            }

            // --- ОПИСАНИЕ (ИЗВЛЕЧЕНИЕ) ---
            let description = "";
            const descElem = card.querySelector(CONFIG.SELECTORS.DESCRIPTION_PREVIEW);
            if (descElem) {
                // Чистим текст от лишних пробелов и переносов
                description = descElem.innerText.replace(/\s+/g, ' ').trim();
            }

            // --- Картинка (Логика выбора) ---
            let imgElem = null;
            // 1. Микроразметка
            imgElem = card.querySelector('img[itemprop="image"]');
            
            // 2. Маркер слайдера (из конфига)
            if (!imgElem) imgElem = card.querySelector(CONFIG.SELECTORS.SLIDER_MARKER);
            
            // 3. Поиск внутри ссылки (исключая логотипы)
            if (!imgElem && urlElem) {
                const candidates = urlElem.querySelectorAll('img');
                for (let img of candidates) {
                    const isLogoContainer = img.closest(CONFIG.SELECTORS.SELLER_LOGO_MARKER);
                    const isLogoAlt = img.alt === "Логотип";
                    const isTooSmall = img.width < 50; 
                    
                    if (!isLogoContainer && !isLogoAlt && !isTooSmall) {
                        imgElem = img;
                        break;
                    }
                }
            }

            // --- Загрузка Base64 ---
            let imageBase64 = null;
            if (imgElem && imgElem.src && !imgElem.src.includes('data:image/gif')) {
                if (!imgElem.complete) await new Promise(r => setTimeout(r, 200));
                imageBase64 = await getBase64FromUrl(imgElem.src);
            }

            return { title, price, url, description, image_base64: imageBase64 };

        } catch (e) {
            console.error("Parse error:", e);
            return null;
        }
    }
};