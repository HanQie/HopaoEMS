# Requirements: HopaoEMS v2 Completion

## Functional Requirements

### 1. Production Log Management (Policy Completion)
- [ ] Implement strict edit/delete policies for production logs.
- [ ] **Washed Logs:** Prevent direct editing/deletion of logs that have already been washed, or require a mandatory undo-wash step.
- [ ] **Session Lock:** Prevent modification of logs currently associated with an active wash session.
- [ ] **Inventory Sync:** Ensure inventory is correctly adjusted when logs are edited or deleted (rollback and re-apply).

### 2. Wash Session Enhancements
- [ ] Implement a detailed view for Wash Sessions showing all associated rolls, lengths, and tasks.
- [ ] Standardize the "Revoke Wash" (Undo) strategy between UI interactions and server-side logic.
- [ ] Ensure "Revoke" correctly resets the `is_washed` status and associated production log flags.

### 3. Dashboard Interactivity (Drill-down)
- [ ] Convert Dashboard KPI cards into interactive links.
- [ ] Clicking a KPI (e.g., "Pending Orders") should navigate to the filtered list view of that entity.
- [ ] Maintain Strict UI standards (no inline JS, use data-attributes or standard links).

### 4. UI/UX Consistency (Rhythm)
- [ ] Audit all list and detail pages for L/C/F macro rhythm consistency.
- [ ] Ensure KPI cards in detail pages follow the same layout pattern as the dashboard.

### 5. Audit Trail
- [ ] Implement a basic activity log for critical actions (Delete, Revoke, Adjust Stock).
- [ ] Track `operator_id` and `timestamp` for these actions.

## Non-Functional Requirements

### 1. Quality Gate Adherence
- All changes must pass `.\gate.bat`.
- No raw CSS classes allowed in templates.
- No interactive JS inside Jinja templates.

### 2. i18n
- All new strings must be added to `seed.*.json` (en, zh-TW, vi).
- Maintain 100% key parity across languages.
