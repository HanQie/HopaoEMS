/**
 * Fabric Stock-In Module
 * Handles: real-time length calculation, dynamic row add (+1/+10), bulk XLSX import
 */

HopaoUI.register('fabric_stock_in', () => {
    const form = document.querySelector('[data-hook="fabric-stockin-form"]');
    if (!form) return;

    console.log('[fabric_stock_in] Module initializing');

    // ── Helpers ──────────────────────────────────────────────────────────────

    const calculateLength = (kg, gyd) => {
        if (!kg || isNaN(kg) || kg <= 0) return null;
        if (!gyd || isNaN(gyd) || gyd <= 0) return null;
        return ((kg * 1000 / gyd) * 0.9144).toFixed(1);
    };

    const updateRow = (row, gyd) => {
        const kgInput = row.querySelector('[data-hook="fabric-stockin-kg"]');
        const lengthDisplay = row.querySelector('[data-hook="fabric-stockin-length"]');
        const lengthInput = row.querySelector('[data-hook="fabric-stockin-length-input"]');
        if (!kgInput || !lengthDisplay || !lengthInput) return;
        const explicitLength = parseFloat(lengthInput.value);
        if (!Number.isNaN(explicitLength) && explicitLength > 0) {
            lengthDisplay.textContent = explicitLength.toFixed(1).replace(/\.0$/, '') + ' m';
            return;
        }
        const length = calculateLength(parseFloat(kgInput.value), gyd);
        lengthDisplay.textContent = length ? length + ' m' : '-';
    };

    // ── State: global GYD & row counter ──────────────────────────────────────

    let globalGYD = parseFloat(form.dataset.gramPerYard);
    const tbody = form.querySelector('[data-hook="stockin-tbody"]');

    // Count existing rows to generate correct field names for new rows
    const getNextIdx = () => {
        if (!tbody) return 1;
        return tbody.querySelectorAll('[data-hook="fabric-stockin-row"]').length + 1;
    };

    // ── Add Rows ──────────────────────────────────────────────────────────────

    const addRows = (n, prefill = []) => {
        if (!tbody) return;

        for (let i = 0; i < n; i++) {
            const idx = getNextIdx();

            // Clone the first row to get the correct CSS structure (already rendered by server)
            const sourceRow = tbody.querySelector('[data-hook="fabric-stockin-row"]');
            if (!sourceRow) return;

            const clone = sourceRow.cloneNode(true);

            // Clear values and rename fields
            clone.querySelectorAll('input[name]').forEach(inp => {
                const baseName = inp.name.replace(/_\d+$/, '');
                inp.name = `${baseName}_${idx}`;
                inp.value = '';
            });

            // Reset length display
            const lengthEl = clone.querySelector('[data-hook="fabric-stockin-length"]');
            if (lengthEl) lengthEl.textContent = '-';

            // Prefill if provided
            const data = prefill[i];
            if (data) {
                const rollInput = clone.querySelector('[data-hook="fabric-stockin-rollno"]');
                const kgInput = clone.querySelector('[data-hook="fabric-stockin-kg"]');
                const remarkInput = clone.querySelector('[data-hook="fabric-stockin-remark"]');
                const lengthInput = clone.querySelector('[data-hook="fabric-stockin-length-input"]');
                if (rollInput) rollInput.value = data.roll_no || '';
                if (kgInput) kgInput.value = data.weight_kg !== undefined ? data.weight_kg : '';
                if (remarkInput) remarkInput.value = data.remark || '';
                if (lengthInput) lengthInput.value = data.length_m !== undefined ? data.length_m : '';
            }

            tbody.appendChild(clone);

            // Calculate length for prefilled rows
            if (prefill[i]) {
                const newRow = tbody.querySelectorAll('[data-hook="fabric-stockin-row"]')[idx - 1];
                if (newRow) updateRow(newRow, globalGYD);
            }
        }
    };

    // ── Event Delegation ──────────────────────────────────────────────────────

    document.addEventListener('click', (e) => {
        const action = e.target.closest('[data-action]')?.dataset.action;
        if (!action) return;

        if (action === 'stockin-add-1') {
            addRows(1);
        } else if (action === 'stockin-add-10') {
            addRows(10);
        } else if (action === 'stockin-bulk-import-open') {
            const panel = document.querySelector('[data-hook="stockin-bulk-panel"]');
            if (panel) panel.removeAttribute('hidden');
        } else if (action === 'stockin-bulk-import-close') {
            const panel = document.querySelector('[data-hook="stockin-bulk-panel"]');
            if (panel) panel.setAttribute('hidden', '');
        } else if (action === 'stockin-bulk-preview') {
            handleBulkPreview();
        } else if (action === 'stockin-bulk-apply') {
            handleBulkApply();
        }
    });

    // ── Real-time length calculation ──────────────────────────────────────────

    form.addEventListener('input', (e) => {
        if (e.target.matches('[data-hook="fabric-stockin-kg"]')) {
            const row = e.target.closest('[data-hook="fabric-stockin-row"]');
            if (row) {
                const gyd = row.dataset.gramPerYard ? parseFloat(row.dataset.gramPerYard) : globalGYD;
                updateRow(row, gyd);
            }
        }
    });

    // Initial calc for pre-filled values
    if (globalGYD && globalGYD > 0) {
        form.querySelectorAll('[data-hook="fabric-stockin-row"]').forEach(row => {
            updateRow(row, row.dataset.gramPerYard ? parseFloat(row.dataset.gramPerYard) : globalGYD);
        });
    }

    // ── Fabric select: reload page ────────────────────────────────────────────

    const fabricSelect = form.querySelector('[data-hook="fabric-select"]');
    if (fabricSelect) {
        fabricSelect.addEventListener('change', (e) => {
            const fabricId = e.target.value;
            const cylInput = form.querySelector('input[name="cylinder_no"]');
            const cylValue = cylInput ? cylInput.value : '';
            window.location.search = `?fabric_id=${fabricId}&cylinder_no=${cylValue}`;
        });
    }

    // ── Bulk XLSX import ──────────────────────────────────────────────────────

    let bulkPreviewData = null;

    const handleBulkPreview = async () => {
        const fileInput = document.querySelector('[data-hook="stockin-bulk-file"] input[type="file"]');
        if (!fileInput || !fileInput.files.length) return;

        const formData = new FormData();
        formData.append('xlsx_file', fileInput.files[0]);

        try {
            const resp = await fetch('/fabric/stock-in/import-xlsx', {
                method: 'POST',
                body: formData
            });
            const data = await resp.json();
            bulkPreviewData = data;

            // Show preview area
            const previewArea = document.querySelector('[data-hook="stockin-bulk-preview-area"]');
            if (previewArea) previewArea.removeAttribute('hidden');

            // Success count
            const successEl = document.querySelector('[data-hook="stockin-bulk-success-count"]');
            if (successEl) successEl.textContent = data.rows.length + ' rows ready';

            // Errors
            const errorsEl = document.querySelector('[data-hook="stockin-bulk-errors"]');
            const failCountEl = document.querySelector('[data-hook="stockin-bulk-fail-count"]');
            const errorListEl = document.querySelector('[data-hook="stockin-bulk-error-list"]');

            if (data.errors && data.errors.length > 0) {
                if (errorsEl) errorsEl.removeAttribute('hidden');
                if (failCountEl) failCountEl.textContent = data.errors.length + ' errors';
                if (errorListEl) {
                    errorListEl.textContent = '';
                    data.errors.forEach(err => {
                        const li = document.createElement('li');
                        li.textContent = err.message;
                        errorListEl.appendChild(li);
                    });
                }
            } else {
                if (errorsEl) errorsEl.setAttribute('hidden', '');
            }
        } catch (err) {
            console.error('[fabric_stock_in] bulk preview error', err);
        }
    };

    const handleBulkApply = () => {
        if (!bulkPreviewData || !bulkPreviewData.rows.length) return;

        const modeInput = document.querySelector('[data-hook="stockin-apply-mode"]:checked');
        const mode = modeInput ? modeInput.value : 'replace';

        if (mode === 'replace' && tbody) {
            // Clear existing rows
            tbody.querySelectorAll('[data-hook="fabric-stockin-row"]').forEach(r => r.remove());
        }

        addRows(bulkPreviewData.rows.length, bulkPreviewData.rows);

        // Close the panel
        const panel = document.querySelector('[data-hook="stockin-bulk-panel"]');
        if (panel) panel.setAttribute('hidden', '');
    };

    console.log('[fabric_stock_in] Module initialized');
});
