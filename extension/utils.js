const randomDelay = (min, max) => new Promise(resolve => setTimeout(resolve, Math.random() * (max - min) + min));

function remoteLog(msg, level = 'info') {
    if (level === 'error') {
        console.error('[Content]', msg);
    } else {
        console.log('[Content]', msg);
    }
}

function highlightElement(element, color="red") {
    if (!element) return;
    const originalBorder = element.style.border;
    element.style.border = `3px solid ${color}`;
    setTimeout(() => { element.style.border = originalBorder; }, 1000);
}

async function getBase64FromUrl(url) {
    if (!url) return null;
    try {
        const response = await fetch(url);
        const blob = await response.blob();
        return new Promise((resolve) => {
            const reader = new FileReader();
            reader.onloadend = () => resolve(reader.result);
            reader.onerror = () => resolve(null);
            reader.readAsDataURL(blob);
        });
    } catch (e) { return null; }
}