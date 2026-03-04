/**
 * Sample List Module
 * Handles View Mode switching (Grid/Table/Lightbox), Search interactions, and Lightbox Overlay.
 * Strict compliance: hidden attribute manipulation only, no forbidden APIs.
 */
(function () {
    const STATE = { mode: localStorage.getItem('sample_view_mode') || 'grid' };

    function init() {
        const root = document.querySelector('[data-hook="sample-list-root"]');
        if (!root) return;

        const gridView = root.querySelector('[data-hook="sample-view-grid"]');
        const tableView = root.querySelector('[data-hook="sample-view-table"]');

        const lightbox = root.querySelector('[data-hook="sample-lightbox"]');
        const lightboxImg = lightbox ? lightbox.querySelector('[data-hook="sample-lightbox-img"]') : null;
        const lightboxTitle = lightbox ? lightbox.querySelector('[data-hook="sample-lightbox-title"]') : null;

        // Mode Buttons (Header actions)
        const modeContainer = document.querySelector('[data-hook="sample-view-mode"]');
        const modeBtns = modeContainer ? modeContainer.querySelectorAll('[data-hook="sample-viewmode-btn"]') : [];

        function updateView(mode) {
            // 1. Toggle Containers
            // Table -> Show Table, Hide Grid
            // Grid/Lightbox -> Show Grid, Hide Table
            let showGrid = (mode !== 'table');

            if (gridView) gridView.hidden = !showGrid;
            if (tableView) tableView.hidden = showGrid;

            // 2. Update Buttons
            modeBtns.forEach(btn => {
                const m = btn.getAttribute('data-mode');
                if (m === mode) {
                    btn.disabled = true; // Active state
                    btn.setAttribute('aria-pressed', 'true');
                } else {
                    btn.disabled = false;
                    btn.setAttribute('aria-pressed', 'false');
                }
            });
        }

        // Initial Render
        updateView(STATE.mode);

        // Event: Mode Switching
        modeBtns.forEach(btn => {
            btn.addEventListener('click', function (e) {
                const mode = btn.getAttribute('data-mode');
                if (mode) {
                    STATE.mode = mode;
                    localStorage.setItem('sample_view_mode', mode);
                    updateView(mode);
                }
            });
        });

        // Event: Root Clicks (Delegation)
        root.addEventListener('click', function (e) {
            // 1. Lightbox Close (Button)
            if (e.target.closest('[data-hook="sample-lightbox-close"]')) {
                closeLightbox();
                return;
            }

            // 2. Lightbox Close (Backdrop)
            if (lightbox && !lightbox.hidden && e.target === lightbox) {
                closeLightbox();
                return;
            }

            // 3. Thumbnail Click
            const thumb = e.target.closest('[data-hook="sample-card-thumb"]');
            if (thumb) {
                // Intercept navigation ONLY in Lightbox mode
                if (STATE.mode === 'lightbox') {
                    e.preventDefault();
                    openLightbox(thumb);
                }
                // Else: allow default navigation (view page)
            }
        });

        // Event: Keyboard (ESC)
        document.addEventListener('keydown', function (e) {
            if (e.key === 'Escape' && lightbox && !lightbox.hidden) {
                closeLightbox();
            }
        });

        function openLightbox(thumb) {
            if (!lightbox || !lightboxImg) return;

            const src = thumb.getAttribute('data-src');
            const title = thumb.getAttribute('data-title');

            lightboxImg.src = src || '';
            if (lightboxTitle) lightboxTitle.textContent = title || '';
            lightbox.hidden = false;
        }

        function closeLightbox() {
            if (lightbox) {
                lightbox.hidden = true;
                if (lightboxImg) lightboxImg.src = ''; // Clear src
            }
        }
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
