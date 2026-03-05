# Project: HopaoEMS v2

## Overview
HopaoEMS v2 is an ERP/EMS (Enterprise Resource Planning / Engineering Management System) specifically designed for digital printing factories. It manages the entire lifecycle of production from orders to final completion, emphasizing strict UI/UX standards and automated quality gates.

## Core Modules
- **Order:** Order creation, task tracking, and closure.
- **Fabric:** Inventory management of fabric rolls and cylinders.
- **Sample:** Design and color management for samples.
- **Ink:** Stock management for printing ink.
- **Production:** Workbench for tracking printing logs and task progress.
- **Wash:** Management of the washing process and vat tracking.

## Technical Stack
- **Backend:** Python (Flask)
- **Frontend:** Jinja2 templates, Vanilla JS (Strict UI Contract)
- **Database:** SQLite
- **Verification:** Custom Quality Gate (`gate.bat`)

## Status & Goal
The project is in an advanced stage (Phase P6 completed). The goal is to reach full "completion" by implementing the remaining roadmap items and ensuring system stability.

## Key Objectives
- Complete production log edit/delete policies.
- Standardize wash session detail views and revoke strategies.
- Implement clickable dashboard KPI drill-downs.
- Unify UI rhythm across all modules.
- Enhance audit trails.
