---
phase: 7
plan: 01-ux-refinement
name: UI/UX Refinement & View Defaults
goal: Set Table view as default for Fabric/Sample, implement single-button toggle, and refine toolbar actions.
type: feature
wave: 1
autonomous: true
files_modified: 5
requirements: [UI-12, UI-13, UI-14, UI-15]
depends_on: []
must_haves:
  truths:
    - name: table_view_is_default
      description: Both Fabric and Sample list pages must default to Table view upon initial load without 'view' parameter.
    - name: single_button_toggle
      description: Switching between Grid and Table views must be done via a single toggle button that changes its icon based on state.
    - name: active_nav_visual
      description: The active module in the top navigation bar must show a clear bottom border (border-slate-900).
  artifacts:
    - path: src/hopaoems/templates/macros/ui/components.html
      provides: Updated ui_view_toggle macro.
    - path: src/static/js/ui/fabric_list_view_mode.js
      provides: Single-button toggle logic for fabrics.
    - path: src/static/js/ui/sample_list_view_mode.js
      provides: Single-button toggle logic for samples.
  key_links:
    - from: ui_view_toggle
      to: fabric_list_view_mode.js
      via: data-action hook
---

# Plan 01-ux-refinement: UI/UX Refinement & View Defaults

<task id="7.1" status="todo">
<name>Update View Toggle Macro & Logic</name>
<files>
  <file>src/hopaoems/templates/macros/ui/components.html</file>
  <file>src/static/js/ui/fabric_list_view_mode.js</file>
  <file>src/static/js/ui/sample_list_view_mode.js</file>
</files>
<action>
Refactor `ui_view_toggle` to a single-button implementation. Update JS logic to handle the toggle action and default to 'table'. 
Ensure icons switch: 'table' icon when in grid mode, 'grid-3x3-gap' icon when in table mode.
</action>
<verify>
<automated>.\gate.bat</automated>
Check: Fabric/Sample lists default to Table. Clicking toggle switches to Grid and back.
</verify>
<done>
View switching is simplified to a single button and defaults to Table.
</done>
</task>

<task id="7.2" status="todo">
<name>Refine Fabric List Toolbar</name>
<files>
  <file>src/hopaoems/templates/fabric/list.html</file>
</files>
<action>
Remove the redundant 'Stock In' button from the list toolbar. It already exists in individual card/row actions.
</action>
<verify>
<automated>.\gate.bat</automated>
Verify 'Stock In' button is gone from the top toolbar but remains in table/card actions.
</verify>
<done>
Fabric toolbar is cleaner and less redundant.
</done>
</task>

<task id="7.3" status="todo">
<name>Fix Navigation Active State (Bottom Line)</name>
<files>
  <file>src/hopaoems/templates/macros/ui/layout.html</file>
</files>
<action>
Verify navigation item matching logic. Ensure the 'Fabrics' link correctly applies the 'border-slate-900' class when active to show the bottom line.
</action>
<verify>
<automated>.\gate.bat</automated>
Visual check: Navigation items show a clear bottom border when active.
</verify>
<done>
Navigation visual feedback is consistent across all main modules.
</done>
</task>
