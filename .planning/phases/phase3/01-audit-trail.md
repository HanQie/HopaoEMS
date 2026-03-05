---
phase: 3
plan: 01-audit-trail
name: Audit Trail Implementation
goal: Create a robust audit logging system to track critical actions across the application.
depends_on: []
must_haves:
  truths:
    - name: audit_log_existence
      description: Critical system actions (Delete, Revoke, Adjust Stock) must be recorded in the audit_logs table.
  artifacts:
    - path: src/hopaoems/services/audit_service.py
      provides: Centralized logging service.
      min_lines: 30
    - path: src/hopaoems/templates/settings/activity.html
      provides: Unified activity feed.
      min_lines: 50
  key_links:
    - from: production_repo.py
      to: audit_service.py
      via: log_action call
---

# Plan 01-audit-trail: Audit Trail Implementation

<task id="3.1" name="Create audit_logs Table" status="todo">
<files>
  <file>src/hopaoems/services/schema_migrations.py</file>
</files>
<action>
Add the `audit_logs` table definition to `init_schema()`. Columns: id (PK), operator_id (FK), action (TEXT), target_entity (TEXT), target_id (INTEGER), timestamp (TIMESTAMP), details (TEXT).
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Check that the DB Schema Gate passes and the table exists in the smoke database.
</verify>
<done>
Database schema updated with audit trail support.
</done>
</task>

<task id="3.2" name="Implement Audit Service" status="todo">
<files>
  <file>src/hopaoems/services/audit_service.py</file>
</files>
<action>
Create a centralized `audit_service.py` with a `log_event(operator_id, action, target_entity, target_id, details=None)` function.
</action>
<verify>
<automated>python -m pytest tests/test_audit_trail.py</automated>
Unit test to verify that calling log_event inserts a record into the database.
</verify>
<done>
Application has a dedicated service for tracking activity.
</done>
</task>

<task id="3.3" name="Integrate Audit Logging" status="todo">
<files>
  <file>src/hopaoems/services/production_repo.py</file>
  <file>src/hopaoems/services/wash_repo.py</file>
  <file>src/hopaoems/services/fabric_repo.py</file>
</files>
<action>
Inject `audit_service.log_event` calls into critical functions: `delete_log`, `undo_log`, `revoke_session`, `adjust_roll_stock`, and `deplete_roll`.
</action>
<verify>
<automated>python src/hopaoems/contracts/smoke_tests.py</automated>
Perform a few critical actions during smoke tests and verify audit entries are created.
</verify>
<done>
Critical system events are now fully traceable.
</done>
</task>
