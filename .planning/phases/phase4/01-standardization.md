---
phase: 4
plan: 01-standardization
name: UI/UX Button & Icon Overhaul
goal: Overhaul all pages to ensure consistent placement and icon logic for buttons, submit, and back actions.
requirements: [UI-01, UI-02, UI-03]
depends_on: []
must_haves:
  truths:
    - name: header_icon_consistency
      description: All 'Back' buttons must be variant='secondary' and use the 'arrow-left' icon. All 'New/Create' buttons in headers must use the 'plus' icon.
    - name: footer_alignment_truth
      description: Form footers must have 'Cancel' (secondary) on the left and 'Submit' (primary, 'check-lg' icon) on the right.
    - name: table_icon_standard
      description: In-table actions must use 'eye' for View, 'pencil' for Edit, and 'trash' for Delete.
  artifacts:
    - path: src/hopaoems/templates/macros/ui/layout.html
      provides: Standardized header/footer rhythm.
      min_lines: 100
  key_links:
    - from: ui_page_header
      to: all_templates
      via: action slot
---

# Plan 01-standardization: UI/UX Button & Icon Overhaul

<task id="4.1" name="Standardize Header Actions" status="todo">
<files>
  <file>src/hopaoems/templates/order/view.html</file>
  <file>src/hopaoems/templates/order/list.html</file>
  <file>src/hopaoems/templates/fabric/list.html</file>
  <file>src/hopaoems/templates/fabric/explorer.html</file>
  <file>src/hopaoems/templates/sample/list.html</file>
  <file>src/hopaoems/templates/sample/view.html</file>
  <file>src/hopaoems/templates/wash/list.html</file>
  <file>src/hopaoems/templates/wash/history.html</file>
  <file>src/hopaoems/templates/production/list.html</file>
  <file>src/hopaoems/templates/production/view.html</file>
</files>
<action>
Update page headers to follow: [Secondary/Back, icon:arrow-left] [Special Actions] [Primary/Create, icon:plus].
</action>
<verify>
<automated>.\gate.bat</automated>
Check visually: Verify 'Back' button variant and icon, and 'New' button icon in headers.
</verify>
<done>
Headers are visually consistent across all major system entities.
</done>
</task>

<task id="4.2" name="Standardize Form Footers" status="todo">
<files>
  <file>src/hopaoems/templates/order/form.html</file>
  <file>src/hopaoems/templates/fabric/roll_adjust_stock.html</file>
  <file>src/hopaoems/templates/fabric/roll_form.html</file>
  <file>src/hopaoems/templates/fabric/cylinder_form.html</file>
  <file>src/hopaoems/templates/sample/form.html</file>
  <file>src/hopaoems/templates/ink/form.html</file>
  <file>src/hopaoems/templates/auth/login.html</file>
</files>
<action>
Refactor form footers to use `ui_form_footer`: left-aligned 'Cancel' link and right-aligned 'Submit' button with 'check-lg' icon.
</action>
<verify>
<automated>.\gate.bat</automated>
Inspect form layouts: Confirm 'Submit' has 'check-lg' icon and is right-most element.
</verify>
<done>
Form submission flows are predictable and uniform.
</done>
</task>

<task id="4.3" name="Standardize Table Action Icons" status="todo">
<files>
  <file>src/hopaoems/templates/macros/ui/components.html</file>
</files>
<action>
Ensure `ui_row_actions` and `ui_row_actions_fixed` use: 'eye' (View), 'pencil' (Edit), 'trash' (Delete).
</action>
<verify>
<automated>.\gate.bat</automated>
Verify icons in list tables (Orders, Samples, Fabrics).
</verify>
<done>
Action icons in tables follow a universal project-wide logic.
</done>
</task>
