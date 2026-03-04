/**
 * Fabric Explorer Module
 * Handles filter interactions (fabric/cylinder search & selection)
 */

HopaoUI.register('fabric_explorer', () => {
    // No-op guard: Only run on fabric explorer page
    const root = document.querySelector('[data-hook="fabric-explorer-root"]');
    if (!root) return;

    console.log('[fabric_explorer] Module initializing');

    // Filter Form Logic
    const filterForm = root.querySelector('[data-hook="fabric-explorer-filter-form"]');
    if (filterForm) {

        // Helper: Submit form
        const submitFilters = () => {
            // Check for requestSubmit support (modern browsers)
            if (typeof filterForm.requestSubmit === 'function') {
                filterForm.requestSubmit();
            } else {
                filterForm.submit();
            }
        };

        // Event Delegation for inputs/selects inside the form
        filterForm.addEventListener('change', (e) => {
            const target = e.target;

            // Matches any of our filter inputs
            if (target.matches('[data-hook="fabric-explorer-fabric-q"]') ||
                target.matches('[data-hook="fabric-explorer-cyl-q"]') ||
                target.matches('[data-hook="fabric-explorer-fabric-select"]') ||
                target.matches('[data-hook="fabric-explorer-cyl-select"]')) {

                submitFilters();
            }
        });

        // Optional: Handle Enter key for text inputs (default form behavior usually handles this, 
        // but explicit handling ensures consistent UX if form structure implies otherwise)
        filterForm.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                const target = e.target;
                if (target.matches('[data-hook="fabric-explorer-fabric-q"]') ||
                    target.matches('[data-hook="fabric-explorer-cyl-q"]')) {
                    // Let default submit happen or force it
                    // Default behavior of Enter in a form is usually submit, so strictly we might not need this
                    // unless we want to prevent default and do something specific.
                    // For now, let's rely on native form behavior for Enter, 
                    // but 'change' event covers the "blur/selection" case.
                }
            }
        });
    }

    console.log('[fabric_explorer] Module initialized');
});
