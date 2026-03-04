/**
 * Wash List Module
 * Handles UI interactions on the wash list page
 */

HopaoUI.register('wash_list', () => {
    // No-op guard: Only run on wash list view
    const root = document.querySelector('[data-hook="wash-list-root"]');
    if (!root) return;

    console.log('[wash_list] Module initializing');

    /**
     * Helper: Scroll to a specific vat group
     * @param {string} vatCode 
     */
    const focusVatGroup = (vatCode) => {
        // Find by data attribute since ID is sanitized
        const group = document.querySelector(`[data-hook="wash-vat-group"][data-vat-code="${vatCode}"]`);
        if (group) {
            group.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    };

    /**
     * Helper: Scroll to a specific sanitized ID
     * @param {string} id 
     */
    const focusById = (id) => {
        const element = document.getElementById(id);
        if (element) {
            element.scrollIntoView({ behavior: 'smooth', block: 'center' });
        }
    };

    // 1. Check for focused vat on load (PRG pattern support)
    const urlParams = new URLSearchParams(window.location.search);
    const focusVat = urlParams.get('focus_vat');
    const hash = window.location.hash;

    if (focusVat) {
        focusVatGroup(focusVat);
    } else if (hash && hash.startsWith('#vat-')) {
        focusById(hash.substring(1));
    }

    // 2. Prevent empty submission (UX enhancement)
    root.addEventListener('submit', (e) => {
        const form = e.target.closest('form');
        if (form && form.querySelector('input[name="log_ids"]')) {
            const checked = form.querySelectorAll('input[name="log_ids"]:checked');
            if (checked.length === 0) {
                e.preventDefault();
                // Simple alert as requested for "A/B" choice (preferring no JS but B allows small enhancement)
                // Actually the requirement said: "攔截並提示（不改 style，只 alert() 或設定某個提示區塊 hidden）"
                alert("Please select at least one log to wash.");
            }
        }
    });

    // 3. Handle Select All
    root.addEventListener('change', function (e) {
        if (e.target.matches('[data-hook="wash-select-all"]')) {
            const form = e.target.closest('form');
            if (!form) return;
            const checkboxes = form.querySelectorAll('[data-hook="wash-log-checkbox"]');
            checkboxes.forEach(cb => cb.checked = e.target.checked);
        }
    });

    console.log('[wash_list] Module initialized');
});
