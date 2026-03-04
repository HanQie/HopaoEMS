/**
 * Production Task Logs Module
 * Handles UI interactions on the production task view and log table
 */

HopaoUI.register('production_task_logs', () => {
    // No-op guard: Only run on production task view
    const root = document.querySelector('[data-hook="production-task-root"]');
    if (!root) return;

    console.log('[production_task_logs] Module initializing');

    /**
     * Helper: Scroll to a specific log row and provide a brief visual highlight
     * @param {string|number} logId 
     */
    const focusLogRow = (logId) => {
        const row = document.getElementById(`log-${logId}`);
        if (row) {
            row.scrollIntoView({ behavior: 'smooth', block: 'center' });

            // Brief "flash" effect handled by data-attribute if CSS support exists, 
            // or just rely on scroll for now to avoid classList manipulation if strict.
            // Since we aren't allowed to use classList, we just scroll.
        }
    };

    // 1. Check for focused log on load (PRG pattern support)
    const urlParams = new URLSearchParams(window.location.search);
    const focusLogId = urlParams.get('focus_log_id');
    const hash = window.location.hash;

    if (focusLogId) {
        focusLogRow(focusLogId);
    } else if (hash && hash.startsWith('#log-')) {
        const id = hash.replace('#log-', '');
        focusLogRow(id);
    }

    // 2. Event delegation for any future log-specific actions
    // (Reserved for edit/delete confirmations or other client-side UX if added later)
    root.addEventListener('click', (e) => {
        // Example: Handle customized attributes or behaviors here
        // const btn = e.target.closest('[data-action="something"]');
    });

    console.log('[production_task_logs] Module initialized');
});
