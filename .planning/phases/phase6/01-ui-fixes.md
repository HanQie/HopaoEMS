---
phase: 6
plan: 01-ui-fixes
name: UI/UX Bug Fixes & i18n Sync
goal: Resolve specific UI switching issues, polish Fabric module layout, and complete i18n for Stock In.
requirements: [UI-07, UI-08, UI-09, UI-10, UI-11]
depends_on: []
must_haves:
  truths:
    - name: view_switching_operational
      description: Both Fabric and Sample modules must successfully switch between Grid and Table views and persist state in URL.
    - name: fabric_header_cleanup
      description: Fabric Explorer header must only contain necessary actions; redundant search/input removed if applicable.
  artifacts:
    - path: src/static/js/ui/fabric_list_view_mode.js
      provides: View switching logic.
    - path: src/hopaoems/templates/fabric/stock_in_form.html
      provides: Standardized i18n strings.
---

# Plan 01-ui-fixes: UI/UX Bug Fixes & i18n Sync

<task id="6.1" name="Fix View Switching Persistence & Logic" status="todo">
<files>
  <file>src/hopaoems/templates/fabric/list.html</file>
  <file>src/hopaoems/templates/sample/list.html</file>
  <file>src/static/js/ui/fabric_list_view_mode.js</file>
  <file>src/static/js/ui/sample_list_view_mode.js</file>
</files>
<action>
Remove conflicting 'hidden' attributes from template wrappers. Ensure JavaScript logic correctly toggles visibility based on URL parameters and clicks.
</action>
<verify>
<automated>.\gate.bat</automated>
Manual: Verify Fabric/Sample switch to Table and back to Grid works and updates URL.
</verify>
<done>
View switching is robust and bidirectional.
</done>
</task>

<task id="6.2" name="Polish Fabric Explorer & Header" status="todo">
<files>
  <file>src/hopaoems/templates/fabric/explorer.html</file>
</files>
<action>
Add bottom border/line to the 'base selection' (search area) if missing. Remove redundant 'Input' action from top header if it duplicates functionality.
</action>
<verify>
<automated>.\gate.bat</automated>
Check Fabric Explorer for clean layout and missing lines.
</verify>
<done>
Fabric module layout is polished and redundant inputs removed.
</done>
</task>

<task id="6.3" name="Stock In i18n Sync" status="todo">
<files>
  <file>src/hopaoems/templates/fabric/stock_in_form.html</file>
  <file>src/hopaoems/translations/en/seed.json</file>
  <file>src/hopaoems/translations/zh-TW/seed.json</file>
  <file>src/hopaoems/translations/vi/seed.json</file>
</files>
<action>
Replace hardcoded 'Fabric GYD:' and other strings in `stock_in_form.html` with `t()` calls. Sync new keys across all translation seeds.
</action>
<verify>
<automated>.\gate.bat</automated>
Check Stock In page in all 3 languages for correct translations.
</verify>
<done>
Stock In page is fully localized.
</done>
</task>
