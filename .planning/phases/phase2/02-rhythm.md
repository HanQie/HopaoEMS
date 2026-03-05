---
phase: 2
plan: 02-rhythm
name: Detail Page Rhythm & UI Logic
goal: Standardize the UI rhythm and data preparation logic for main detail pages.
depends_on: []
must_haves:
  truths:
    - name: mother_pattern_rhythm
      description: All detail pages must follow the Header -> Summary Grid -> Content Cards sequence.
  artifacts:
    - path: src/hopaoems/templates/order/view.html
      provides: Reference Mother Pattern implementation.
      min_lines: 100
    - path: src/hopaoems/blueprints/ui_order.py
      provides: Consistent VM preparation logic.
      min_lines: 100
  key_links:
    - from: ui_fabric.py
      to: fabric/explorer.html
      via: stats object
---

# Plan 02-rhythm: Detail Page Rhythm & UI Logic

<task id="2.1" name="Audit and Standardize UI Logic" status="todo">
<files>
  <file>src/hopaoems/blueprints/ui_order.py</file>
  <file>src/hopaoems/blueprints/ui_fabric.py</file>
  <file>src/hopaoems/blueprints/ui_sample.py</file>
</files>
<action>
Audit how summary data is prepared for detail pages. Ensure `ui_fabric.fabric_explorer` and `ui_sample.sample_view` provide a flat, easy-to-render 'stats' object for the KPI grid.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Check that each view function returns a structured stats object consistent with the requirements of 'ui_stat_grid'.
</verify>
<done>
UI logic consistently prepares summary data for rendering.
</done>
</task>

<task id="2.2" name="Harmonize Detail Page Layouts" status="todo">
<files>
  <file>src/hopaoems/templates/fabric/explorer.html</file>
  <file>src/hopaoems/templates/sample/view.html</file>
</files>
<action>
Refactor `explorer.html` and `sample/view.html` to strictly follow the Mother Pattern rhythm. Use `ui_stat_grid` for top-level summaries and ensure consistent `ui_container` usage.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Visual audit of detail pages: Verify KPI row at top and consistent information hierarchy.
</verify>
<done>
Main detail pages exhibit a unified and professional layout rhythm.
</done>
</task>

<task id="2.3" name="Standardize List Page Rhythm" status="todo">
<files>
  <file>src/hopaoems/templates/ink/list.html</file>
  <file>src/hopaoems/templates/sample/list.html</file>
</files>
<action>
Verify and polish list page layouts for Ink and Samples. Ensure `ui_list_toolbar` is used with correct slot alignment and consistent spacing.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Visual audit of list pages: check toolbar alignment and table density.
</verify>
<done>
List pages adhere to the global UI workstation standards.
</done>
</task>
