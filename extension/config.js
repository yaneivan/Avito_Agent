const CONFIG = {
    TARGET_COUNT: 100,       
    MAX_EMPTY_SCROLLS: 5,
    
    // Флаг: Делать ли новую вкладку активной? (true = переключаться на нее)
    // Это ускоряет работу скриптов в браузере.
    OPEN_IN_ACTIVE_TAB: true, 
    
    // Задержки (в мс)
    START_DELAY: { MIN: 1500, MAX: 3000 },
    SCROLL_DELAY: { MIN: 2000, MAX: 3500 },
    ITEM_DELAY: { MIN: 50, MAX: 150 },
    
    // Селекторы элементов на странице
    SELECTORS: {
        ITEM_CARD: '[data-marker="item"]',
        // Селектор для текста описания в выдаче (ищем по специфичному стилю)
        DESCRIPTION_PREVIEW: 'p[style*="--module-max-lines-size"]',
        
        // Маркеры для фото
        PHOTO_MARKER: '[data-marker*="item-photo"] img',
        SLIDER_MARKER: '[data-marker*="slider-image"] img',
        SELLER_LOGO_MARKER: '[data-marker="item-user-logo"]'
    }
};