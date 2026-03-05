---
phase: 3
plan: 02-activity-view
name: Activity View & Root Cleanup
goal: Provide visibility into the audit trail and clean up redundant project files.
depends_on: ["01-audit-trail"]
must_haves:
  truths:
    - name: file_cleanliness
      description: Redundant log and debug files must be removed from the root directory.
  artifacts:
    - path: src/hopaoems/templates/settings/activity.html
      provides: Visual activity log for operators.
      min_lines: 50
  key_links:
    - from: ui_settings.py
      to: activity.html
      via: audit_logs query
---

# Plan 02-activity-view: Activity View & Root Cleanup

<task id="3.4" name="Implement Activity Route" status="todo">
<files>
  <file>src/hopaoems/blueprints/ui_settings.py</file>
</files>
<action>
Add a `/activity` route to the settings blueprint. Fetch the latest 50 records from `audit_logs` joined with `users`.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Ensure the new route is registered and accessible by operators.
</verify>
<done>
Activity log is accessible via the web interface.
</done>
</task>

<task id="3.5" name="Create Activity Template" status="todo">
<files>
  <file>src/hopaoems/templates/settings/activity.html</file>
</files>
<action>
Create the template using the Mother Pattern. Show a table of activities with relative timestamps and clear action descriptions.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Visual audit of the Activity page.
</verify>
<done>
Activity log follows the project's strict UI rhythm.
</done>
</task>

<task id="3.6" name="Root Directory Cleanup" status="todo">
<files>
  <file>.</file>
</files>
<action>
Identify and remove redundant `.txt`, `.log`, and `.sqlite` files from the root directory that are not part of the core project structure or quality gates.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Ensure that deleting these files does not break any quality gates or automated tests.
</verify>
<done>
Project root is clean and ready for hand-over.
</done>
</task>
