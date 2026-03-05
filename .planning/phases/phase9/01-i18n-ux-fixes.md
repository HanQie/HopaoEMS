---
phase: 9
plan: 01-i18n-ux-fixes
name: Final i18n & UX Polish
goal: Correct i18n translations, fix Stock In page internationalization, and restore/unify inbound operations in Fabric table.
type: feature
wave: 1
autonomous: true
files_modified: 6
requirements: [UI-16, UI-17, UI-18]
depends_on: []
must_haves:
  truths:
    - name: grid_mode_translated
      description: 'common.view_mode.grid' must be correctly translated across all 3 languages (English, Chinese, Vietnamese).
    - name: fabric_table_stock_in
      description: The Fabric list table view must have a clear 'Stock In' action for each row.
  artifacts:
    - path: src/hopaoems/templates/fabric/list.html
      provides: Unified Stock In actions.
    - path: src/hopaoems/i18n/seed.zh-TW.json
      provides: Correct Chinese translations.
---

# Plan 01-i18n-ux-fixes: Final i18n & UX Polish

<task id="9.1" status="todo">
<name>Fix i18n Translations</name>
<files>
  <file>src/hopaoems/i18n/seed.zh-TW.json</file>
  <file>src/hopaoems/i18n/seed.vi.json</file>
  <file>src/hopaoems/i18n/seed.en.json</file>
</files>
<action>
Correct 'common.view_mode.grid' in `seed.zh-TW.json` (Change 'Chế độ Lưới' to '網格檢視'). 
Audit all Stock In related keys (`fabric.stock_in.*`) to ensure they are complete and consistent across all three languages.
</action>
<verify>
<automated>.\gate.bat</automated>
Check translation seeds for consistency.
</verify>
<done>
International support for Grid Mode and Stock In is fully verified.
</done>
</task>

<task id="9.2" status="todo">
<name>Restore & Unify Fabric Stock In Actions</name>
<files>
  <file>src/hopaoems/templates/fabric/list.html</file>
</files>
<action>
1. Restore the global 'Stock In' button to the `ui_list_toolbar` in the Fabric List (it's useful for quick entry without pre-selecting a fabric).
2. Add a 'Stock In' icon-button (`box-seam` icon) to the table row actions in the Table View to match the Grid View capabilities.
</action>
<verify>
<automated>.\gate.bat</automated>
Check: Fabric Table View now has a 'Stock In' button per row. Top toolbar has a global 'Stock In' button.
</verify>
<done>
Inbound operations are easily accessible in all views of the Fabric module.
</done>
</task>
