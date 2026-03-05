---
phase: 2
plan: 01-dashboard
name: Dashboard Interactivity & Logic
goal: Refactor dashboard data to support dynamic drill-down links and update the UI.
depends_on: []
must_haves:
  truths:
    - name: dynamic_link_data
      description: Dashboard stats must include target URLs/link targets provided by the backend.
  artifacts:
    - path: src/hopaoems/blueprints/ui_main.py
      provides: Link-enriched dashboard stats.
      min_lines: 50
    - path: src/hopaoems/templates/index.html
      provides: Clickable KPI cards.
      min_lines: 30
  key_links:
    - from: ui_main.py
      to: index.html
      via: stats dictionary
---

# Plan 01-dashboard: Dashboard Interactivity & Logic

<task id="1.1" name="Refactor ui_main.py dashboard data" status="todo">
<files>
  <file>src/hopaoems/blueprints/ui_main.py</file>
</files>
<action>
Update the `index` route to include specific link targets for each KPI in the stats dictionary, ensuring the backend defines where each KPI should navigate.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Check that the stats dictionary passed to the template contains 'href' or 'target' keys for all main KPIs.
</verify>
<done>
Dashboard logic provides consistent navigation targets.
</done>
</task>

<task id="1.2" name="Update dashboard.html KPIs" status="todo">
<files>
  <file>src/hopaoems/templates/index.html</file>
</files>
<action>
Update the `ui_stat_grid` call to use the links provided by the backend stats object. Ensure all KPI cards are wrapped in or function as links.
</action>
<verify>
<automated>python -m hopaoems.contracts.run_gates</automated>
Visually verify that clicking any dashboard KPI card navigates to the correct filtered list.
</verify>
<done>
Dashboard KPIs are fully interactive and link-driven.
</done>
</task>
