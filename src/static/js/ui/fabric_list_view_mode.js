/**
 * Fabric List - View Mode Switcher
 * Handles switching between cards/grid (same mode) and table view modes.
 * Grid and Cards are aliases for the same view.
 * Strict compliance: No classList, No innerHTML, No style manipulation.
 */

HopaoUI.register('fabric_list_view_mode', () => {
    const root = document.querySelector('[data-hook="fabric-list-root"]');
    if (!root) return;

    const cardsPanel = root.querySelector('[data-hook="fabric-cards-panel"]');
    const tablePanel = root.querySelector('[data-hook="fabric-table-panel"]');

    if (!cardsPanel || !tablePanel) return;

    // Get current view from URL or default to 'table'
    const params = new URLSearchParams(window.location.search);
    const currentView = params.get('view') || 'table';

    // Set initial state
    if (currentView === 'table') {
        cardsPanel.hidden = true;
        tablePanel.hidden = false;
    } else {
        cardsPanel.hidden = false;
        tablePanel.hidden = true;
    }

    // Handle view mode switching
    document.addEventListener('click', (e) => {
        const toggleBtn = e.target.closest('[data-action="fabric-view-toggle"]');
        if (!toggleBtn) return;

        e.preventDefault();
        const isCurrentlyTable = !tablePanel.hidden;
        const icon = toggleBtn.querySelector('i');
        const span = toggleBtn.lastChild; // The label text node

        if (isCurrentlyTable) {
            // Switch to Grid
            cardsPanel.hidden = false;
            tablePanel.hidden = true;
            if (icon) icon.className = 'bi bi-table mr-2 -ml-1'; 
            if (span && span.nodeType === Node.TEXT_NODE) {
                span.textContent = ' ' + (HopaoUI.translate('common.view_mode.table') || 'Table View');
            }

            const url = new URL(window.location);
            url.searchParams.set('view', 'grid');
            window.history.replaceState({}, '', url);
        } else {
            // Switch to Table
            cardsPanel.hidden = true;
            tablePanel.hidden = false;
            if (icon) icon.className = 'bi bi-grid-3x3-gap mr-2 -ml-1';
            if (span && span.nodeType === Node.TEXT_NODE) {
                span.textContent = ' ' + (HopaoUI.translate('common.view_mode.grid') || 'Grid View');
            }

            const url = new URL(window.location);
            url.searchParams.set('view', 'table');
            window.history.replaceState({}, '', url);
        }
    });
});
