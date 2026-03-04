/**
 * Sidebar Toggle Logic
 * Handles sidebar expansion/collapse with localStorage persistence.
 *
 * Targets:
 * - .js-toggle-sidebar (trigger button)
 * - #sidebar-expanded (expanded sidebar element)
 * - #sidebar-collapsed (collapsed sidebar element)
 */

HopaoUI.register('sidebar_toggle', () => {
    const toggleBtn = document.querySelector('.js-toggle-sidebar');
    const sidebarExpanded = document.getElementById('sidebar-expanded');
    const sidebarCollapsed = document.getElementById('sidebar-collapsed');

    // Storage Key (Namespaced)
    const STORAGE_KEY = 'hopaoems_sidebar_expanded';

    // Exit if elements missing (e.g., login page)
    if (!toggleBtn || !sidebarExpanded || !sidebarCollapsed) {
        return;
    }

    /**
     * Apply sidebar state (Strict: hidden attribute only)
     * @param {boolean} isExpanded
     */
    const applyState = (isExpanded) => {
        if (isExpanded) {
            sidebarExpanded.hidden = false;
            sidebarCollapsed.hidden = true;
            toggleBtn.setAttribute('aria-expanded', 'true');
        } else {
            sidebarExpanded.hidden = true;
            sidebarCollapsed.hidden = false;
            toggleBtn.setAttribute('aria-expanded', 'false');
        }
    };

    // 1. Init: Load from storage (default: true)
    const savedState = localStorage.getItem(STORAGE_KEY);
    const isExpanded = savedState === null ? true : (savedState === 'true');
    applyState(isExpanded);

    // 2. Toggle Handler
    toggleBtn.addEventListener('click', (e) => {
        e.preventDefault();

        // Toggle based on current expanded visibility
        const isCurrentlyCollapsed = sidebarExpanded.hidden;
        const newState = isCurrentlyCollapsed; // true = expand, false = collapse

        applyState(newState);
        localStorage.setItem(STORAGE_KEY, newState.toString());
    });
});
