---
phase: 1
plan: 01-logic
name: Core Production Logic Guardrails
goal: Implement strict server-side checks for washed and locked logs in the repository layer.
depends_on: []
must_haves:
  truths:
    - name: washed_log_protection
      description: Length changes on washed logs are prohibited at the repository level unless explicitly forced.
  artifacts:
    - path: src/hopaoems/services/production_repo.py
      provides: Strict log validation logic.
      min_lines: 500
  key_links:
    - from: production_repo.py
      to: wash_repo.py
      via: log_id validation
---

# Plan 01-logic: Core Production Logic Guardrails

<task id="1.1" name="Refactor production_repo.update_log" status="todo">
<files>
  <file>src/hopaoems/services/production_repo.py</file>
</files>
<action>
Modify `update_log` to explicitly check if a log is "washed" or "session-locked" before allowing length changes. Allow note-only updates. Add `force_undo` parameter.
</action>
<verify>
<automated>python -m pytest tests/test_production_backend.py</automated>
Check that length updates on washed logs fail without force flag.
</verify>
<done>
Length changes on washed logs are blocked by default.
</done>
</task>

<task id="1.2" name="Refactor production_repo.delete_log" status="todo">
<files>
  <file>src/hopaoems/services/production_repo.py</file>
</files>
<action>
Update `delete_log` to block deletion of logs that are already washed or currently assigned to a wash session.
</action>
<verify>
<automated>python -m pytest tests/test_production_backend.py</automated>
Ensure deleting a washed log raises a ValueError.
</verify>
<done>
Washed logs cannot be deleted directly.
</done>
</task>

<task id="1.3" name="Implement check_log_lock" status="todo">
<files>
  <file>src/hopaoems/services/production_repo.py</file>
</files>
<action>
Implement `check_log_lock(log_id)` to return True if the log is in a wash session that hasn't been finalized (if applicable) or simply if it has a `wash_session_id`.
</action>
<verify>
<automated>python -m pytest tests/test_production_backend.py</automated>
Verify lock status for logs in and out of sessions.
</verify>
<done>
Lock check function is available and used in guardrails.
</done>
</task>
