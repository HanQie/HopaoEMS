/**
 * Order Form - Dynamic Items Management
 * Handles adding/removing order items and populating initial data.
 */
HopaoUI.register('order_form_items', () => {
    const root = document.querySelector('[data-hook="order-form-root"]');
    if (!root) return;

    const container = root.querySelector('[data-hook="items-container"]');
    const template = root.querySelector('[data-hook="item-template"]');
    const addBtn = root.querySelector('[data-action="add-item"]');

    if (!container || !template) return;

    let index = 0;

    function bindRow(row) {
        const removeBtn = row.querySelector('[data-action="remove-item"]');
        if (removeBtn) {
            removeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                row.remove();
            });
        }
    }

    function addItem(data = null) {
        const clone = template.content.cloneNode(true);
        const row = clone.querySelector('[data-hook="order-item-row"]');

        // Replace INDEX in all inputs/selects
        row.querySelectorAll('input, select, textarea').forEach(el => {
            const rawName = el.name || el.getAttribute('name');
            if (rawName) el.name = rawName.replace('INDEX', index);
            if (el.id) el.id = el.id.replace('INDEX', index);

            // Populate data if provided
            if (data) {
                if (el.dataset.hook === 'js-item-id') el.value = data.id || '';
                else if (el.name.includes('[fabric_no]')) el.value = data.fabric_no || '';
                else if (el.name.includes('[sample_id]')) el.value = data.sample_id || '';
                else if (el.name.includes('[qty]')) el.value = data.qty || '';
                else if (el.name.includes('[note]')) el.value = data.note || '';
            }
        });

        bindRow(row);
        container.appendChild(clone);
        index++;
    }

    // Event Listeners
    if (addBtn) {
        addBtn.addEventListener('click', (e) => {
            e.preventDefault();
            addItem();
        });
    }

    // Initial Population: Scan existing SSR rows
    const existingRows = container.querySelectorAll('[data-hook="order-item-row"]');
    if (existingRows.length > 0) {
        existingRows.forEach(row => bindRow(row));
        index = existingRows.length; // Set next index
    } else {
        addItem(); // Default one empty row if none
    }
});
