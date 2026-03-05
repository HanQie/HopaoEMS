---
phase: 5
plan: 01-placement-contract
name: Unified Action Placement Contract
goal: Enforce a strict placement pattern for primary and secondary actions across all subpages to ensure operational consistency.
requirements: [UI-04, UI-05, UI-06]
depends_on: []
must_haves:
  truths:
    - name: zero_primary_in_cards
      description: Primary Submit/Commit buttons must never be placed inside cards; they must reside in the Header or Form Footer.
    - name: footer_rhythm_truth
      description: All forms must use the justify-between ui_form_footer with Cancel/Back on the left and Submit on the right.
  artifacts:
    - path: src/hopaoems/templates/fabric/stock_in_form.html
      provides: Reference for complex form action layout.
      min_lines: 80
  key_links:
    - from: ui_form_footer
      to: all_templates
      via: placement standardization
---

# Plan 01-placement-contract: Unified Action Placement Contract

<task id="5.1" name="Standardize Fabric Stock-In Form" status="todo">
<files>
  <file>src/hopaoems/templates/fabric/stock_in_form.html</file>
</files>
<action>
Refactor `stock_in_form.html`: Move the 'Commit' button to a `ui_form_footer`. Reorder header: Back (arrow-left) first, then 'Add Fabric'.
</action>
<verify>
<automated>.\gate.bat</automated>
Visual audit: Verify 'Commit' is in footer and 'Back' is left-most in header.
</verify>
<done>
Stock-In form perfectly adheres to the layout contract.
</done>
</task>

<task id="5.2" name="Refactor Production Workflow Pages" status="todo">
<files>
  <file>src/hopaoems/templates/production/produce.html</file>
  <file>src/hopaoems/templates/production/view.html</file>
  <file>src/hopaoems/templates/production/test_consume.html</file>
</files>
<action>
Refactor Production pages: In `view.html`, move 'Produce' and 'Complete' actions from the card to the Page Header. In `produce.html` and `test_consume.html`, move 'Cancel' to Header Back.
</action>
<verify>
<automated>.\gate.bat</automated>
Ensure primary actions are NOT inside cards in Production views.
</verify>
<done>
Production actions are consolidated in headers/footers.
</done>
</task>

<task id="5.3" name="Global Subpage Alignment Sweep" status="todo">
<files>
  <file>src/hopaoems/templates/order/rework_form.html</file>
  <file>src/hopaoems/templates/order/form.html</file>
  <file>src/hopaoems/templates/sample/form.html</file>
  <file>src/hopaoems/templates/ink/form.html</file>
  <file>src/hopaoems/templates/production/log_edit.html</file>
  <file>src/hopaoems/templates/fabric/roll_adjust_stock.html</file>
  <file>src/hopaoems/templates/fabric/cylinder_form.html</file>
</files>
<action>
Verify and align all remaining forms: Use `ui_form_footer` with Cancel-Left/Submit-Right. Ensure 'Back' is first in all headers.
</action>
<verify>
<automated>.\gate.bat</automated>
Final sweep of all listed templates.
</verify>
<done>
100% convergence achieved across all Create/Edit/Commit subpages.
</done>
</task>
