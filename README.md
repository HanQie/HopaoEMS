# HopaoEMS Quick Start

Welcome to the HopaoEMS (Enterprise Management System). This repository contains the source code for managing the fabric supply chain, from stock intake to order processing and washing.

## Getting Started (Boot)

To run the application locally in development mode:
1. Ensure `python` is installed and the `.venv/` is active or exists.
2. Double-click or run `boot.bat` from your terminal.
3. Access the application at `http://localhost:5000`.

## Testing & Quality Control (Gate)

Before committing changes, you **must** run the gate script:
1. Double check the app is running.
2. Execute `gate.bat` or `.\gate.bat` in PowerShell.
3. This will run the smoke tests (Pytest + Playwright) against the current codebase. Ensure all tests pass.

## Roles & Access Control

The app uses a strict Role-Based Access Control (RBAC) dual-role system:
- **Operator** (`operator`): Has read/write permissions. Can create orders, mutate fabric stock, register wash sessions, and modify system settings. (Note: Legacy `admin` roles have been migrated to `operator`).
- **Viewer** (`viewer`): Has read-only permissions. Can view all dashboards, tracking logs, and lists, but cannot modify data.

## Internationalization (i18n)

The application supports robust i18n out-of-the-box:
- **Dictionary**: `src/hopaoems/i18n/seed.*.json`
- **UI Swapper**: Use the `/__debug/i18n` endpoint to debug missing keys, or simply use the UI language toggle if enabled.
- All template strings must use `_('key')` or `t('key')` macros instead of hardcoding text.

## Module Navigation Sequence

When exploring or testing the app, follow this natural supply chain flow:
1. **Dashboard** (`/`): High-level KPIs and entry point.
2. **Fabric** (`/fabric/`): Inventory of generic fabrics, registration of physical cylinders and rolls.
3. **Samples** (`/sample/`): Color-matching lab samples pointing to specific fabric stocks.
4. **Orders** (`/order/`): Client orders requesting specific samples x fabrics.
5. **Production** (`/production/`): Fulfilling order items by consuming physical fabric rolls.
6. **Wash** (`/wash/`): Processing consumed rolls in vats to complete the production lifecycle.

## Database & Instance Behavior

The application uses SQLite databases stored in `src/hopaoems/instance/` and generated assets (like sample images) stored in `src/data/uploads/`.
- **Untracked by Design**: All `.sqlite` databases and upload artifacts are inherently runtime data and are **strictly excluded** from version control (`.gitignore`).
- **Initialization**: On boot, if `hopaoems.sqlite` does not exist, `boot.bat` (via `create_app()`) automatically initializes the schema from `schema_migrations.py` and seeds default users.

## Macro-Only UI Contract

To enforce 100% UI consistency across the app, raw HTML tags (like `<button>`, `<input>`, `<table>`) are largely forbidden in page templates. 
- All standard UI elements MUST be rendered using the Jinja2 macros defined in `src/hopaoems/templates/macros/ui/`.
- For more granular system constraints (JS delegation, Single-Scroll principles, etc.), please refer to `docs/spec/ARCHITECTURE.md`.
