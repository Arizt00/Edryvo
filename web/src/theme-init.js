try {
    const requested = new URLSearchParams(location.search).get('theme');
    const saved = localStorage.getItem('lumen.theme');
    const theme = requested || saved || 'day';
    document.documentElement.dataset.theme = ['day', 'dark', 'forest'].includes(theme) ? theme : 'day';
} catch (_) {
    document.documentElement.dataset.theme = 'day';
}
