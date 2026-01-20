const Actions = {
    /**
     * Плавный скролл вниз
     */
    humanScroll: async function(pixels) {
        let scrolled = 0;
        const step = Math.floor(Math.random() * 40) + 30; 
        
        while (scrolled < pixels) {
            window.scrollBy(0, step);
            scrolled += step;
            await randomDelay(10, 30);
            
            if ((window.innerHeight + window.scrollY) >= document.body.scrollHeight) {
                break;
            }
        }
    },

    /**
     * (Заготовка на будущее) Ввод текста в поле
     * @param {string} selector - селектор input
     * @param {string} text - текст
     */
    typeText: async function(selector, text) {
        const input = document.querySelector(selector);
        if (!input) return false;

        input.focus();
        // Тут будет сложная логика эмуляции нажатий клавиш
        // input.value = text;
        // input.dispatchEvent(new Event('input', { bubbles: true }));
        return true;
    }
};