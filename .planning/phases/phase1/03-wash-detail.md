---
phase: 1
plan: 03-wash-detail
name: Wash Session Detail & Revocation
goal: Implement a dedicated wash session detail view and unify the revocation strategy.
depends_on: ["01-logic"]
must_haves:
  truths:
    - name: unified_revocation
      description: Revoking a session must use the same logic as individual log undos to maintain consistency.
  artifacts:
    - path: src/hopaoems/templates/wash/detail.html
      provides: Detailed observability into wash sessions.
      min_lines: 50
  key_links:
    - from: ui_wash.py
      to: wash_repo.py
      via: session_id
---

# Plan 03-wash-detail: Wash Session Detail & Revocation

<task id="3.1" name="Implement session detail route" status="todo">
<files>
  <file>src/hopaoems/blueprints/ui_wash.py</file>
</files>
<action>
Add `wash_session_view(id)` route to fetch session data and associated logs.
</action>
<verify>
<automated>python -m pytest tests/test_all_routes.py</automated>
Navigate to `/wash/session/<id>` and verify 200 status.
</verify>
<done>
Wash session detail endpoint is functional.
</done>
</task>

<task id="3.2" name="Create wash detail template" status="todo">
<files>
  <file>src/hopaoems/templates/wash/detail.html</file>
</files>
<action>
Create `wash/detail.html` using L/C/F macros. Include KPI cards for total length, roll count, and task count. Show a table of all included logs.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Visual check of the new detail page for rhythm and data accuracy.
</verify>
<done>
Wash detail page is implemented and follows UI contract.
</done>
</task>

<task id="3.3" name="Standardize Revoke action" status="todo">
<files>
  <file>src/hopaoems/services/wash_repo.py</file>
</files>
<action>
Refactor `revoke_session` to ensure it triggers the correct inventory and task status pullbacks by delegating to existing `undo_log` logic for each log in the session.
</action>
<verify>
<automated>python -m pytest tests/test_production_backend.py</automated>
Revoke a session and verify all logs return to 'unwashed' and task status is pulled back if needed.
</verify>
<done>
Revocation is robust and consistent with individual log undos.
</done>
</task>
