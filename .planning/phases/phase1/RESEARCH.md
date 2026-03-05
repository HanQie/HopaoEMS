# Phase 1 Research: Production Log & Wash Strategy

## Current State
- `production_repo.py`: Contains `update_log` and `delete_log` with "Auto Undo" logic. This logic automatically reverts washed status if the length changes.
- `wash_repo.py`: Contains `revoke_session` and `undo_log`. `revoke_session` clears `washed_at` and `wash_session_id` for all logs in a session and triggers `sync_status_pullback`.
- `ui_production.py`: Routes `production_log_edit` and `production_log_delete` currently rely on the repo's internal logic.

## Findings
- The "Auto Undo" behavior in `production_repo.py` might be too aggressive or non-compliant with the "mandatory undo-wash step" requirement if we want users to explicitly acknowledge the change.
- There is no specific "Wash Session Detail" view; history is shown in a table with expandable rows, but a dedicated detail page would allow for better observability and actions like "Revoke".
- Inventory sync is handled in `update_log` but needs careful verification when the length is updated (rollback old deduction, apply new deduction).

## Risks
- Incorrect inventory calculation during concurrent edits.
- Status mismatch if `sync_status_pullback` fails or is skipped.
