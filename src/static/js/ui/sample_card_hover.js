/**
 * Sample Card Hover Interactions
 * Handles showing/hiding action buttons overlay on card hover.
 * Uses mouseenter/mouseleave to avoid flickering issues.
 * Strict compliance: No classList, No innerHTML, No style manipulation.
 */

HopaoUI.register('sample_card_hover', () => {
    // We use event delegation on the document or a root container if possible,
    // but mouseenter/mouseleave don't bubble well for delegation.
    // So we attach listeners to existing cards and observe for new ones.

    const attachListeners = (card) => {
        if (card.dataset.hoverAttached === 'true') return;

        const actionsOverlay = card.querySelector('[data-hook="sample-card-actions"]');
        if (!actionsOverlay) return;

        card.addEventListener('mouseenter', () => {
            actionsOverlay.hidden = false;
        });

        card.addEventListener('mouseleave', (e) => {
            // Check if we moved to a child element (shouldn't happen with mouseleave but good safety)
            if (card.contains(e.relatedTarget)) return;
            actionsOverlay.hidden = true;
        });

        // Accessibility: Show on focus within card
        card.addEventListener('focusin', () => {
            actionsOverlay.hidden = false;
        });

        // Hide on focusout if moving outside card
        card.addEventListener('focusout', (e) => {
            if (!card.contains(e.relatedTarget)) {
                actionsOverlay.hidden = true;
            }
        });

        card.dataset.hoverAttached = 'true';
    };

    // Initialize existing cards
    document.querySelectorAll('[data-hook="sample-card"]').forEach(attachListeners);

    // Observer for dynamic content (e.g. infinite scroll or view switching)
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element
                    if (node.matches && node.matches('[data-hook="sample-card"]')) {
                        attachListeners(node);
                    } else if (node.querySelectorAll) {
                        node.querySelectorAll('[data-hook="sample-card"]').forEach(attachListeners);
                    }
                }
            });
        });
    });

    const root = document.querySelector('[data-hook="sample-list-root"]');
    if (root) {
        observer.observe(root, { childList: true, subtree: true });
    } else {
        // Fallback to body if specific root not found yet
        observer.observe(document.body, { childList: true, subtree: true });
    }
});
