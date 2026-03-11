/**
 * Sample Form - Section Management
 * Handles toggle of selections panel and summary count updates.
 */
HopaoUI.register('sample_form_sections', () => {
    const root = document.querySelector('[data-hook="sample-form-root"]');
    if (!root) return;

    const toggleBtn = root.querySelector('[data-hook="sample-selections-toggle"]');
    const panel = root.querySelector('[data-hook="sample-selections-panel"]');
    const counter = root.querySelector('[data-hook="sample-selections-count"]');
    const tbody = root.querySelector('[data-hook="cc-tbody"]');

    function updateSummary() {
        if (!counter || !tbody) return;
        const count = tbody.querySelectorAll('[data-hook="cc-row"]').length;
        const pattern = counter.dataset.pattern || "Selections: {count}";
        counter.textContent = pattern.replace('{count}', count);
    }

    function togglePanel(visible) {
        if (!panel) return;
        panel.hidden = !visible;
        if (toggleBtn) {
            const label = visible
                ? toggleBtn.dataset.labelHide
                : toggleBtn.dataset.labelShow;
            if (label) toggleBtn.textContent = label;
        }
    }

    if (toggleBtn && panel) {
        toggleBtn.addEventListener('click', (e) => {
            e.preventDefault();
            togglePanel(panel.hidden);
        });
    }

    // Auto-update counter whenever table changes
    if (tbody && counter) {
        const observer = new MutationObserver(() => {
            updateSummary();
        });
        observer.observe(tbody, { childList: true });
        updateSummary(); // Initial run
    }
});
