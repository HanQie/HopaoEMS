# Roadmap: HopaoEMS v2 Completion

## Phase 1: Production Log & Wash Strategy (High Impact)
**Goal:** Solidify the "Washed/Unwashed/Locked" status logic and ensure inventory integrity.

### Tasks
- [ ] Implement and verify `edit/delete` policies in `ui_production.py` and `production_service.py`.
- [ ] Add strict status checks in the `POST` endpoints.
- [ ] Implement the "Revoke Wash" detail view and unify the logic with the production log status updates.
- [ ] Verify with new smoke tests (e.g., trying to delete a washed log).

## Phase 2: Dashboard Drill-down & UI Rhythm (UX Polish)
**Goal:** Make the application feel "connected" and ensure visual consistency.

### Tasks
- [ ] Refactor `ui_main.py` dashboard data to include filter link targets.
- [ ] Update `dashboard.html` to use clickable card wrappers or standard link-driven UI components.
- [ ] Audit `ui_order.py`, `ui_fabric.py`, and `ui_sample.py` detail pages for rhythm consistency.
- [ ] Ensure all list pages have consistent `toolbar` and `tabs` layouts (Strict 2-slot contract).

## Phase 3: Audit Trail & Final Cleanup: **COMPLETED**

## Phase 4: UI/UX Button & Icon Overhaul: **COMPLETED**

## Phase 5: Unified Action Placement Contract: **COMPLETED**

## Phase 6: UI/UX Bug Fixes & i18n Sync: **COMPLETED**

## Phase 7: UI/UX Refinement & View Defaults: **COMPLETED**

## Phase 8: Wash Workstation Redesign: **COMPLETED**

## Phase 9: Final i18n & UX Polish
**Goal:** Address final i18n inconsistencies and restore critical inbound operations.

### Requirements
- **UI-16:** Correct 'Grid Mode' translation in Chinese.
- **UI-17:** Audit and sync all Stock In i18n keys.
- **UI-18:** Restore and unify Stock In actions in Fabric List (Toolbar + Table Rows).

## Success Criteria
- [ ] 'Grid Mode' is '網格檢視' in Chinese.
- [ ] Fabric Table View has per-row Stock In actions.
- [ ] Global Stock In button is back in the toolbar.
- [ ] `.\gate.bat` passes.
