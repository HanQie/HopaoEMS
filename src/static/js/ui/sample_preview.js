/**
 * Sample Preview Module
 * Handles TIFF preview, color picking via lightbox modal, and color correction draft management.
 * Strict compliance: No classList, No innerHTML, No style manipulation.
 */

HopaoUI.register('sample_preview', () => {
    const previewFile = document.querySelector('[data-hook="sample-preview-file"]');
    if (!previewFile) return;

    const DRAFT_KEY = 'sample_cc_draft';
    let currentObjectURL = null;
    let pickerCanvas = null;
    let pickerCtx = null;

    const HOOKS = {
        CC_TBODY: 'cc-tbody',
        CC_ROW_TEMPLATE: 'cc-row-template',
        CC_EMPTY: 'cc-empty',
        CC_TABLE: 'cc-table',
        CC_ERROR: 'cc-error',
        CC_ERROR_MSG: 'cc-error-msg',
        ROW_SWATCH: 'row-source-swatch',
        ROW_RGB_TEXT: 'cc-row-rgb',
        LAB_BLOCK: 'cc-lab-block',
        NOTE_BLOCK: 'cc-note-block',
        PREVIEW_IMG: 'sample-preview-img',
        PREVIEW_FILE: 'sample-preview-file',
        PREVIEW_PLACEHOLDER: 'sample-preview-placeholder',
        PREVIEW_OPEN_PICKER: 'sample-preview-open-picker',
        PICKER_MODAL: 'sample-picker-modal',
        PICKER_IMG: 'sample-picker-img',
        PICKER_CLOSE: 'sample-picker-close',
        PICKER_STATUS: 'sample-picker-status',
        PICKED_RGB: 'picked-rgb'  // Contract hook for RGB display
    };

    const ACTIONS = {
        ADD: 'cc-add',  // Contract action (primary)
        ADD_ALT: 'sample-add-selection',  // Alternative hook
        REMOVE_ROW: 'cc-remove-row',
        CLEAR: 'cc-clear',
        MODE: 'cc-mode'
    };

    const getH = (name) => `[data-hook="${HOOKS[name]}"]`;
    const getA = (name) => `[data-hook="${ACTIONS[name]}"]`;

    // Helper: Save current rows state to sessionStorage
    const saveDraft = () => {
        const body = document.querySelector(getH('CC_TBODY'));
        if (!body) return;
        const rows = body.querySelectorAll('[data-hook="cc-row"]');
        const data = Array.from(rows).map(row => {
            const r = row.querySelector('[name="cc_r"]')?.value;
            if (r === undefined) return null;
            return {
                r: r,
                g: row.querySelector('[name="cc_g"]')?.value,
                b: row.querySelector('[name="cc_b"]')?.value,
                mode: row.querySelector('[name="cc_mode"]')?.value,
                l: row.querySelector('[name="cc_l"]')?.value,
                a: row.querySelector('[name="cc_a"]')?.value,
                b2: row.querySelector('[name="cc_b2"]')?.value,
                note: row.querySelector('[name="cc_note"]')?.value,
                hex: row.querySelector(getH('ROW_SWATCH'))?.src
            };
        }).filter(item => item !== null);
        sessionStorage.setItem(DRAFT_KEY, JSON.stringify(data));
    };

    const rgbToHex = (r, g, b) => {
        return "#" + ((1 << 24) + (parseInt(r) << 16) + (parseInt(g) << 8) + parseInt(b)).toString(16).slice(1).toUpperCase();
    };

    const updateContainerState = () => {
        const body = document.querySelector(getH('CC_TBODY'));
        const empty = document.querySelector(getH('CC_EMPTY'));
        const table = document.querySelector(getH('CC_TABLE'));
        if (body && empty && table) {
            const rowCount = body.querySelectorAll('[data-hook="cc-row"]').length;
            const hasRows = rowCount > 0;
            empty.hidden = hasRows;
            table.hidden = !hasRows;

            const countDisplay = document.querySelector('[data-hook="sample-selections-count"]');
            if (countDisplay && countDisplay.dataset.pattern) {
                countDisplay.textContent = countDisplay.dataset.pattern.replace('{count}', rowCount);
            }
        }
    };

    const applyModeVisibility = (row) => {
        const mode = row.querySelector('[name="cc_mode"]')?.value || 'lab';
        const labBlock = row.querySelector(getH('LAB_BLOCK'));
        const noteBlock = row.querySelector(getH('NOTE_BLOCK'));
        if (labBlock) labBlock.hidden = (mode !== 'lab');
        if (noteBlock) noteBlock.hidden = (mode !== 'note');
        const radio = row.querySelector(`input[type="radio"][value="${mode}"]`);
        if (radio) radio.checked = true;
    };

    const addRow = (item) => {
        const body = document.querySelector(getH('CC_TBODY'));
        const template = document.querySelector(getH('CC_ROW_TEMPLATE'));
        if (!body || !template) return;

        const clone = template.content.cloneNode(true);
        const row = clone.querySelector('[data-hook="cc-row"]');
        if (!row) return;

        const uniqueId = 'mode_' + Date.now() + '_' + Math.random().toString(36).substr(2, 5);
        row.querySelectorAll('input[type="radio"]').forEach(radio => radio.name = uniqueId);

        const fields = {
            cc_r: item.r, cc_g: item.g, cc_b: item.b,
            cc_mode: item.mode || 'lab', cc_l: item.l || '',
            cc_a: item.a || '', cc_b2: item.b2 || '', cc_note: item.note || ''
        };

        for (const [name, val] of Object.entries(fields)) {
            const input = row.querySelector(`[name="${name}"]`);
            if (input) input.value = val;
        }

        applyModeVisibility(row);

        const hex = item.hex || `/data/swatches/${rgbToHex(item.r, item.g, item.b).replace('#', '')}.png`;
        const swatch = row.querySelector(getH('ROW_SWATCH'));
        if (swatch) swatch.src = hex;

        const rgbText = row.querySelector(getH('ROW_RGB_TEXT'));
        if (rgbText) rgbText.textContent = `RGB ${item.r}, ${item.g}, ${item.b}`;

        body.appendChild(clone);
        updateContainerState();
    };

    // Initial Load
    const tbody = document.querySelector(getH('CC_TBODY'));
    if (tbody) {
        tbody.querySelectorAll('tr').forEach(applyModeVisibility);
        const saved = sessionStorage.getItem(DRAFT_KEY);
        if (saved) {
            try { JSON.parse(saved).forEach(addRow); } catch (e) { }
        }
    }

    // File handling
    const previewContainer = document.querySelector(getH('PREVIEW_OPEN_PICKER'));
    if (previewContainer) {
        ['dragenter', 'dragover'].forEach(evt => {
            previewContainer.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                previewContainer.dataset.dragover = "1";
            });
        });

        ['dragleave', 'drop'].forEach(evt => {
            previewContainer.addEventListener(evt, (e) => {
                e.preventDefault();
                e.stopPropagation();
                delete previewContainer.dataset.dragover;
            });
        });

        previewContainer.addEventListener('drop', (e) => {
            const dt = e.dataTransfer;
            if (dt && dt.files && dt.files.length > 0) {
                const input = document.querySelector(getH('PREVIEW_FILE'));
                if (input) {
                    input.files = dt.files;
                    input.dispatchEvent(new Event('change', { bubbles: true }));
                }
            }
        });
    }

    document.addEventListener('change', (e) => {
        const input = e.target.closest(getH('PREVIEW_FILE'));
        if (input && input.files && input.files[0]) {
            const file = input.files[0];
            const img = document.querySelector(getH('PREVIEW_IMG'));
            const placeholder = document.querySelector(getH('PREVIEW_PLACEHOLDER'));
            const pickerImg = document.querySelector(getH('PICKER_IMG'));
            const isTiff = file.name.toLowerCase().endsWith('.tif') || file.name.toLowerCase().endsWith('.tiff') || file.type === 'image/tiff';

            sessionStorage.removeItem(DRAFT_KEY);
            const tbody = document.querySelector(getH('CC_TBODY'));
            if (tbody) tbody.textContent = '';
            updateContainerState();

            if (img && currentObjectURL) URL.revokeObjectURL(currentObjectURL);

            if (isTiff && typeof UTIF !== 'undefined') {
                const reader = new FileReader();
                reader.onload = (event) => {
                    const buffer = event.target.result;
                    const ifds = UTIF.decode(buffer);
                    UTIF.decodeImage(buffer, ifds[0]);
                    const rgba = UTIF.toRGBA8(ifds[0]);
                    const canvas = document.createElement('canvas');
                    canvas.width = ifds[0].width; canvas.height = ifds[0].height;
                    const ctx = canvas.getContext('2d');
                    const imgData = ctx.createImageData(canvas.width, canvas.height);
                    imgData.data.set(rgba);
                    ctx.putImageData(imgData, 0, 0);
                    canvas.toBlob((blob) => {
                        currentObjectURL = URL.createObjectURL(blob);
                        img.src = currentObjectURL; img.hidden = false;
                        if (pickerImg) pickerImg.src = currentObjectURL;
                        if (placeholder) placeholder.hidden = true;
                        pickerCanvas = null; pickerCtx = null;
                    }, 'image/png');
                };
                reader.readAsArrayBuffer(file);
            } else {
                currentObjectURL = URL.createObjectURL(file);
                img.src = currentObjectURL; img.hidden = false;
                if (pickerImg) pickerImg.src = currentObjectURL;
                pickerCanvas = null; pickerCtx = null;
                if (placeholder) placeholder.hidden = true;
            }
        }
    });

    // ===== PICKER MODAL LOGIC =====
    const initPickerModal = () => {
        const modal = document.querySelector(getH('PICKER_MODAL'));
        if (!modal) return;

        const pickerImg = document.querySelector(getH('PICKER_IMG'));
        const closeBtn = document.querySelector(getH('PICKER_CLOSE'));
        const openTrigger = document.querySelector(getH('PREVIEW_OPEN_PICKER'));
        // Support both contract action and alternative hook
        const addBtn = document.querySelector(`[data-action="${ACTIONS.ADD}"]`) || document.querySelector(getA('ADD_ALT'));
        const previewImg = document.querySelector(getH('PREVIEW_IMG'));

        const openModal = () => {
            if (!previewImg || previewImg.hidden) return;
            if (pickerImg && previewImg.src) pickerImg.src = previewImg.src;
            modal.hidden = false;
        };

        const closeModal = () => {
            modal.hidden = true;
        };

        // Open modal: click compact preview OR click "Add Selection"
        if (openTrigger) {
            openTrigger.addEventListener('click', (e) => {
                e.preventDefault();
                openModal();
            });
        }

        if (addBtn) {
            addBtn.addEventListener('click', (e) => {
                e.preventDefault();
                openModal();
            });
        }

        // Close modal
        if (closeBtn) {
            closeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                closeModal();
            });
        }

        // Pick color from modal image
        if (pickerImg) {
            pickerImg.addEventListener('click', (e) => {
                const rect = pickerImg.getBoundingClientRect();
                const x = e.clientX - rect.left;
                const y = e.clientY - rect.top;

                if (!pickerCanvas || pickerCanvas.width !== pickerImg.naturalWidth || pickerCanvas.height !== pickerImg.naturalHeight) {
                    pickerCanvas = document.createElement('canvas');
                    pickerCanvas.width = pickerImg.naturalWidth; pickerCanvas.height = pickerImg.naturalHeight;
                    pickerCtx = pickerCanvas.getContext('2d', { willReadFrequently: true });
                    pickerCtx.drawImage(pickerImg, 0, 0);
                }

                const nx = Math.max(0, Math.min(pickerImg.naturalWidth - 1, Math.floor((x / rect.width) * pickerImg.naturalWidth)));
                const ny = Math.max(0, Math.min(pickerImg.naturalHeight - 1, Math.floor((y / rect.height) * pickerImg.naturalHeight)));
                const data = pickerCtx.getImageData(nx, ny, 1, 1).data;
                const [r, g, b] = data;

                addRow({ r, g, b, mode: 'lab' });
                saveDraft();

                const panel = document.querySelector('[data-hook="sample-selections-panel"]');
                if (panel) panel.hidden = false;
                const toggleBtn = document.querySelector('[data-hook="sample-selections-toggle"]');
                if (toggleBtn && toggleBtn.dataset.labelHide) {
                    toggleBtn.textContent = toggleBtn.dataset.labelHide;
                }

                closeModal();
            });
        }
    };

    initPickerModal();

    // Interaction handling
    document.addEventListener('click', (e) => {
        // Toggle detail
        const toggleBtn = e.target.closest('[data-action="cc-toggle-detail"]');
        if (toggleBtn) {
            e.preventDefault();
            const row = toggleBtn.closest('[data-hook="cc-row"]');
            if (row) {
                const collapsed = row.querySelector('[data-hook="cc-collapsed-view"]');
                const expanded = row.querySelector('[data-hook="cc-expanded-view"]');
                if (collapsed && expanded) {
                    const isHidden = expanded.hidden;
                    expanded.hidden = !isHidden;
                    collapsed.hidden = !isHidden;

                    const icon = toggleBtn.querySelector('i');
                    if (icon) {
                        icon.className = isHidden ? 'bi bi-chevron-up' : 'bi bi-pencil';
                    }
                }
            }
        }

        // Remove row
        const removeBtn = e.target.closest('[data-action="cc-remove-row"]');
        if (removeBtn) {
            e.preventDefault();
            const row = removeBtn.closest('[data-hook="cc-row"]');
            if (row) row.remove();
            updateContainerState();
            saveDraft();
        }

        // Clear All
        const clearBtn = e.target.closest(getA('CLEAR'));
        if (clearBtn) {
            e.preventDefault();
            const tbody = document.querySelector(getH('CC_TBODY'));
            if (tbody) tbody.textContent = '';
            updateContainerState();
            sessionStorage.removeItem(DRAFT_KEY);
        }
    });

    document.addEventListener('change', (e) => {
        const modeRadio = e.target.closest('input[type="radio"][data-action="cc-mode"]');
        if (modeRadio) {
            const row = modeRadio.closest('[data-hook="cc-row"]');
            const hiddenInput = row.querySelector('[name="cc_mode"]');
            if (hiddenInput) {
                hiddenInput.value = modeRadio.value;
                applyModeVisibility(row);
                saveDraft();
            }
        }
    });

    document.addEventListener('input', (e) => {
        if (e.target.closest(getH('CC_TBODY'))) saveDraft();
    });

    document.addEventListener('submit', (e) => {
        const form = e.target.closest('form');
        if (form && form.querySelector('[name="cc_r"]')) sessionStorage.removeItem(DRAFT_KEY);
    });
});
