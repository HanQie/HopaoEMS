---
phase: 8
plan: 01-wash-redesign
name: Wash Workstation Redesign
goal: Redesign the Wash Workstation to use a pure table view and a separate registration page for marking washed fabrics.
type: feature
wave: 1
autonomous: true
files_modified: 4
requirements: [WASH-01, WASH-02]
depends_on: []
must_haves:
  truths:
    - name: wash_list_is_tabular
      description: The main Wash Workstation page must display all pending vat groups in a single unified table.
    - name: separate_registration_page
      description: Creating a wash session (marking as washed) must occur on a dedicated sub-page, not inline in the list.
  artifacts:
    - path: src/hopaoems/templates/wash/list.html
      provides: Redesigned tabular workstation view.
    - path: src/hopaoems/templates/wash/register.html
      provides: New registration form page.
  key_links:
    - from: ui_wash.wash_list
      to: ui_wash.wash_register
      via: Register button in table
---

# Plan 01-wash-redesign: Wash Workstation Redesign

<task id="8.1" status="todo">
<name>Create Register Wash Session Page</name>
<files>
  <file>src/hopaoems/blueprints/ui_wash.py</file>
  <file>src/hopaoems/templates/wash/register.html</file>
</files>
<action>
Implement a new GET route `/wash/register/<vat_code>` that shows all unwashed logs for a specific vat. Create the `register.html` template using the Mother Pattern (Header, KPI Grid, Table, Standard Footer).
</action>
<verify>
<automated>.\gate.bat</automated>
Check visually: Navigation to `/wash/register/VAT123` displays a professional form with Mother Pattern rhythm.
</verify>
<done>
Separate registration page is functional and follows UI standards.
</done>
</task>

<task id="8.2" status="todo">
<name>Redesign Wash Workstation List</name>
<files>
  <file>src/hopaoems/templates/wash/list.html</file>
</files>
<action>
Replace the card-stack layout with a single table. Columns: Vat Code, Roll Count, Total Length, Pending Logs, Actions. 
The 'Action' column should have a 'Register' button linking to the new page.
</action>
<verify>
<automated>.\gate.bat</automated>
Check visually: The Wash page is now a clean table. Each row has a 'Register' button.
</verify>
<done>
Wash Workstation is purely tabular and streamlined.
</done>
</task>
