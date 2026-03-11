
/**
 * Hopaoems UI Core (v2.0)
 * Responsible for:
 * 1. Global Utilities (Hooks, Formatters)
 * 2. Module Registry & Boot
 */

const HopaoUI = (() => {
    const modules = {};

    return {
        /**
         * Register a UI module
         * @param {string} name - Unique module name
         * @param {Function} initFn - Initialization function
         */
        register: (name, initFn) => {
            if (modules[name]) {
                console.warn(`[HopaoUI] Module '${name}' already registered.`);
                return;
            }
            modules[name] = initFn;
        },

        /**
         * Boot all registered modules
         */
        boot: () => {
            console.log(`[HopaoUI] Booting ${Object.keys(modules).length} modules...`);
            Object.keys(modules).forEach(name => {
                try {
                    modules[name]();
                } catch (e) {
                    console.error(`[HopaoUI] Failed to boot module '${name}':`, e);
                }
            });
        }
    };
})();

// Expose globally for modules to register
window.HopaoUI = HopaoUI;

document.addEventListener('DOMContentLoaded', () => {
    // 1. Core Utilities Init (Legacy functions still here for now)
    initDynamicRows();
    initConfirmPolicy();
    initTableFilter();
    initUserMenu();
    initLangMenu();
    // initSidebarToggle moved to module
    initLightbox();
    initNavigation();
    // initSampleLocalPreview moved to module
    initRollPicker();

    // 2. Boot Registered Modules
    HopaoUI.boot();

    // 3. Simple Interaction Toggles
    initWashHistoryToggle();
    initFileInputs();

    // 4. QR Code Modal
    initQRCodeModal();
});

/**
 * Initialize native file inputs wrapped by ui_file_input macro
 */
function initFileInputs() {
    document.addEventListener('change', (e) => {
        if (e.target.type === 'file') {
            const input = e.target;
            const filenameDisplay = document.querySelector(`[data-hook="${input.id || input.name}-filename"]`);
            if (filenameDisplay) {
                if (input.files && input.files.length > 0) {
                    filenameDisplay.textContent = input.files[0].name;
                    filenameDisplay.hidden = false;
                } else {
                    filenameDisplay.textContent = '';
                    filenameDisplay.hidden = true;
                }
            }
        }
    });
}



/**
 * Initialize navigation helpers
 * Targets: .js-navigate[data-href]
 */
function initNavigation() {
    document.addEventListener('click', (e) => {
        const btn = e.target.closest('.js-navigate');
        if (btn) {
            e.preventDefault();
            const href = btn.dataset.href;
            if (href && !btn.hasAttribute('disabled')) {
                window.location.href = href;
            }
        }
    });
}

/**
 * Initialize dynamic row behavior for tables
 * Targets: .js-add-row, .js-remove-row
 */
function initWashHistoryToggle() {
    document.addEventListener('click', (e) => {
        const toggleBtn = e.target.closest('[data-action="wash-history-toggle"]');
        if (toggleBtn) {
            e.preventDefault();
            const targetId = toggleBtn.dataset.target;
            if (targetId) {
                const targetEl = document.getElementById(targetId);
                if (targetEl) {
                    targetEl.hidden = !targetEl.hidden;
                }
            }
        }
    });
}
function initDynamicRows() {
    document.addEventListener('click', (e) => {
        const target = e.target.closest('.js-add-row');
        if (target) {
            e.preventDefault();
            const tableId = target.dataset.targetTable;
            const templateId = target.dataset.template;

            const table = document.getElementById(tableId);
            const template = document.getElementById(templateId);

            if (table && template) {
                const tbody = table.querySelector('tbody');
                const clone = template.content.cloneNode(true);
                tbody.appendChild(clone);

                // Trigger customized event if needed
                table.dispatchEvent(new CustomEvent('rowAdded', { bubbles: true }));
            }
        }

        const removeTarget = e.target.closest('.js-remove-row');
        if (removeTarget) {
            e.preventDefault();
            const row = removeTarget.closest('tr');
            if (row) {
                const table = row.closest('table');
                row.remove();

                if (table) {
                    table.dispatchEvent(new CustomEvent('rowRemoved', { bubbles: true }));
                }
            }
        }
    });
}

/**
 * Initialize confirmation policy for forms
 * Targets: form[data-confirm]
 */
function initConfirmPolicy() {
    document.addEventListener('submit', (e) => {
        const form = e.target.closest('form[data-confirm]');
        if (form) {
            const message = form.getAttribute('data-confirm');
            if (message && !window.confirm(message)) {
                e.preventDefault();
            }
        }
    });
}

/**
 * Initialize table filtering logic
 * Targets: .js-filter (inputs)
 */
/**
 * Initialize table filtering logic (Optimized)
 * Targets: .js-filter (inputs)
 * Requirement: Must have data-target pointing to table ID/selector
 */
/**
 * Initialize table filtering logic (Optimized)
 * Targets: .js-filter (inputs)
 * Requirement: Must have data-target pointing to table ID/selector
 */
function initTableFilter() {
    let timeout = null;

    document.addEventListener('input', (e) => {
        const input = e.target.closest('.js-filter');
        if (input) {
            const targetSelector = input.dataset.target;
            // Strict requirement: Must have data-target to avoid full page scan
            if (!targetSelector) return;

            // Debounce 200ms
            clearTimeout(timeout);
            timeout = setTimeout(() => {
                const filterValue = input.value.toLowerCase();
                const targetTable = document.querySelector(targetSelector);

                if (targetTable) {
                    // Optimized: Only query active rows if possible, but here we scan all tbody tr
                    const rows = targetTable.querySelectorAll('tbody tr');

                    // Simple text content scan (can be refined to specific columns if needed)
                    rows.forEach(row => {
                        const text = row.textContent.toLowerCase();
                        row.hidden = !text.includes(filterValue);
                    });
                }
            }, 200);
        }
    });
}

/**
 * Initialize user menu interaction
 * Targets: .js-user-menu-toggle, .js-user-menu-panel
 */
function initUserMenu() {
    document.addEventListener('click', (e) => {
        const toggle = e.target.closest('.js-user-menu-toggle');

        if (toggle) {
            e.preventDefault();
            e.stopPropagation();

            const targetId = toggle.dataset.target;
            let panel;

            // Handle prefix ID selector or direct ID
            if (targetId && targetId.startsWith('user-menu-panel-')) {
                if (document.getElementById(targetId)) panel = document.getElementById(targetId);
            } else if (document.getElementById(targetId)) {
                panel = document.getElementById(targetId);
            } else if (targetId && document.querySelector(targetId)) {
                panel = document.querySelector(targetId);
            }

            if (panel) {
                panel.hidden = !panel.hidden;
            }
        } else {
            // Click outside - close all panels
            const panel = e.target.closest('.js-user-menu-panel');
            if (!panel) {
                document.querySelectorAll('.js-user-menu-panel').forEach(p => {
                    p.hidden = true;
                });
            }
        }
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            document.querySelectorAll('.js-user-menu-panel').forEach(p => {
                p.hidden = true;
            });
        }
    });
}


/**
 * Initialize lightbox functionality
 * Targets: .js-lightbox-open (triggers), #lightbox (overlay)
 * Uses hidden attribute only, no style manipulation
 */
function initLightbox() {
    const lightbox = document.getElementById('lightbox');
    if (!lightbox) return;

    const lightboxImg = lightbox.querySelector('#lightbox-image');
    const lightboxClose = lightbox.querySelector('#lightbox-close');

    // Event delegation for opening lightbox
    document.addEventListener('click', function (e) {
        const trigger = e.target.closest('.js-lightbox-open');
        if (trigger) {
            e.preventDefault();
            const src = trigger.dataset.src;
            if (src && lightboxImg) {
                lightboxImg.src = src;
                lightbox.hidden = false;
            }
        }
    });

    // Close on close button
    if (lightboxClose) {
        lightboxClose.addEventListener('click', function () {
            lightbox.hidden = true;
        });
    }

    // Close on background click
    lightbox.addEventListener('click', function (e) {
        if (e.target === lightbox) {
            lightbox.hidden = true;
        }
    });

    // Close on Esc key
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && !lightbox.hidden) {
            lightbox.hidden = true;
        }
    });
}


/**
 * Initialize Quick Produce Roll Picker
 * Targets: data-hook="roll-cyl-filter", roll-search, roll-groups, pick-roll
 */
function initRollPicker() {
    const container = document.querySelector('[data-hook="roll-groups"]');
    if (!container) return; // Exit if not on produce page

    const cylFilter = document.querySelector('[data-hook="roll-cyl-filter"]');
    const rollSearch = document.querySelector('[data-hook="roll-search"]');
    const summary = document.querySelector('[data-hook="roll-selected-summary"]');
    const hiddenInput = document.querySelector('[data-hook="roll-id-input"]');

    // Filter Logic
    const applyFilters = () => {
        const cylValue = cylFilter ? cylFilter.value.toLowerCase().trim() : '';
        const searchValue = rollSearch ? rollSearch.value.toLowerCase().trim() : '';

        const groups = container.querySelectorAll('[data-hook="roll-group"]');

        groups.forEach(group => {
            const groupCyl = (group.dataset.cylinder || '').toLowerCase();
            const items = group.querySelectorAll('[data-action="pick-roll"]');

            // 1. Group Cylinder Filter (Prefix)
            const cylMatch = !cylValue || groupCyl.startsWith(cylValue);

            let hasVisibleItem = false;

            // 2. Item Search Filter (Contains) & Group visibility
            items.forEach(item => {
                const label = (item.dataset.rollLabel || '').toLowerCase();
                const searchMatch = !searchValue || label.includes(searchValue);

                item.hidden = !searchMatch;
                if (searchMatch) hasVisibleItem = true;
            });

            // Group Visibility: Must match cylinder prefix AND have at least one visible item (search match)
            group.hidden = !(cylMatch && hasVisibleItem);
        });
    };

    if (cylFilter) {
        cylFilter.addEventListener('input', () => { setTimeout(applyFilters, 150); });
    }
    if (rollSearch) {
        rollSearch.addEventListener('input', () => { setTimeout(applyFilters, 150); });
    }

    // Pick Logic
    container.addEventListener('click', (e) => {
        // Handle click on item or inside item
        const item = e.target.closest('[data-action="pick-roll"]');
        if (item) {
            e.preventDefault();

            // 1. Update Input & Summary
            const rollId = item.dataset.rollId;
            const label = item.dataset.rollLabel;

            if (hiddenInput) hiddenInput.value = rollId;

            let prefix = "";
            if (summary && summary.dataset.prefix) prefix = summary.dataset.prefix;

            if (summary) summary.textContent = (prefix ? prefix + " " : "") + label;

            // 2. Update Indicators
            const allItems = container.querySelectorAll('[data-action="pick-roll"]');
            allItems.forEach(i => {
                const ind = i.querySelector('[data-hook="picked-indicator"]');
                if (ind) ind.hidden = true;
            });

            const currentInd = item.querySelector('[data-hook="picked-indicator"]');
            if (currentInd) currentInd.hidden = false;
        }
    });
}


/**
 * Initialize Language Menu (Strict Contract)
 * Trigger: [data-action="lang-menu-toggle"]
 * Target: [data-hook="lang-menu"]
 * Behavior: Toggle hidden, aria-expanded, outside click close.
 */
function initLangMenu() {
    const triggerSelector = '[data-action="lang-menu-toggle"]';
    const menuHook = 'lang-menu';

    document.addEventListener('click', (e) => {
        const trigger = e.target.closest(triggerSelector);

        if (trigger) {
            e.preventDefault();
            e.stopPropagation();

            const targetId = trigger.dataset.target; // "lang-menu"
            const menu = document.querySelector(`[data-hook="${targetId}"]`);

            if (menu) {
                const isHidden = menu.hidden;
                menu.hidden = !isHidden;
                trigger.setAttribute('aria-expanded', !isHidden);
            }
        } else {
            // Outside click logic
            const menu = e.target.closest(`[data-hook="${menuHook}"]`);
            if (!menu) {
                // Click was outside menu and outside trigger (handled above)
                const openMenus = document.querySelectorAll(`[data-hook="${menuHook}"]:not([hidden])`);
                openMenus.forEach(m => {
                    m.hidden = true;
                    // Find corresponding trigger and update aria
                    const t = document.querySelector(`[data-target="${m.dataset.hook}"]`);
                    if (t) t.setAttribute('aria-expanded', 'false');
                });
            }
        }
    });

    // Handle Item Selection (Optional: close menu on click)
    document.addEventListener('click', (e) => {
        const item = e.target.closest('[data-action="lang-menu-select"]');
        if (item) {
            // Allow default navigation, but close menu
            const menu = item.closest(`[data-hook="${menuHook}"]`);
            if (menu) {
                menu.hidden = true;
                const t = document.querySelector(`[data-target="${menu.dataset.hook}"]`);
                if (t) t.setAttribute('aria-expanded', 'false');
            }
        }
    });

    // Escape Key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const openMenus = document.querySelectorAll(`[data-hook="${menuHook}"]:not([hidden])`);
            openMenus.forEach(m => {
                m.hidden = true;
                const t = document.querySelector(`[data-target="${m.dataset.hook}"]`);
                if (t) t.setAttribute('aria-expanded', 'false');
            });
        }
    });
}

/**
 * Initialize Mobile Login QR Code Modal
 * Targets: [data-action="qr-modal-open"], [data-action="qr-modal-close"], #qr-modal, #qr-code-container
 */
function initQRCodeModal() {
    let qrInst = null;

    document.addEventListener('click', (e) => {
        // Open Modal
        const openBtn = e.target.closest('[data-action="qr-modal-open"]');
        if (openBtn) {
            e.preventDefault();
            const modal = document.getElementById('qr-modal');
            const container = document.getElementById('qr-code-container');
            const urlText = document.getElementById('qr-code-url-text');

            if (modal && container) {
                // Get current origin (e.g. http://192.168.1.5:8080)
                const currentUrl = window.location.origin;

                // Set the text
                if (urlText) urlText.textContent = currentUrl;

                // Generate QR (only once or override)
                container.replaceChildren(); // clear previous

                if (typeof QRCode !== 'undefined') {
                    qrInst = new QRCode(container, {
                        text: currentUrl,
                        width: 200,
                        height: 200,
                        colorDark: "#000000",
                        colorLight: "#ffffff",
                        correctLevel: QRCode.CorrectLevel.H
                    });
                } else {
                    container.textContent = 'QR Code library failed to load.';
                }

                modal.hidden = false;
            }
        }

        // Close Modal
        const closeBtn = e.target.closest('[data-action="qr-modal-close"]');
        if (closeBtn) {
            e.preventDefault();
            const modal = document.getElementById('qr-modal');
            if (modal) modal.hidden = true;
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const modal = document.getElementById('qr-modal');
            if (modal && !modal.hidden) {
                modal.hidden = true;
            }
        }
    });
}
