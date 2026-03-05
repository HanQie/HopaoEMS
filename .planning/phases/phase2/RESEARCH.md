# Phase 2 Research: Dashboard Drill-down & UI Rhythm

## Current State
- **Dashboard (`index.html`):** Already has drill-down links for the main 4 KPIs.
- **Order List:** Uses `ui_list_toolbar` with tabs. Correct pattern.
- **Fabric List:** Uses `ui_list_toolbar`. Correct pattern.
- **Sample List:** Uses `ui_list_toolbar` with view mode toggle. Correct pattern.
- **Ink List:** Uses `ui_list_toolbar`. Correct pattern.
- **Order View:** Starts with 4-col KPI grid. Correct Mother Pattern.
- **Fabric Explorer:** Starts with 6-col KPI grid. Slightly different rhythm but acceptable for dense data.
- **Sample View:** Uses individual `ui_stat_card` calls inside a grid.

## Audit Findings
- **Sample View Rhythm:** The `sample/view.html` uses `ui_stat_card` inside a grid but could be cleaner if consolidated into `ui_stat_grid`.
- **Spacing Consistency:** Most pages use `ui_container` correctly, but some card headers vs toolbar spacing might need a final polish.
- **Action Links:** Ensure all "primary" links (like order numbers) in tables use `A.ui_action_link` or consistent `tone`.

## Risks
- Excessive standardization might reduce visibility for dense detail pages (e.g., Fabric Explorer).
- Breaking existing hooks while refactoring templates.
