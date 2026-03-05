# Presentation Layer: Pages & Forms

This document specifies the page layouts, UI macro usage, role-based access control (RBAC), and i18n requirements for the core pages in the application.

## Global Page Structure
- **Navigation & Layout**: Uses `base.html` providing a top nav bar and a main content area.
- **i18n**: 100% of UI strings (titles, table headers, buttons, placeholders, flash messages) are localized using `_()` or `t()`. Keys reside in `src/hopaoems/i18n/`.
- **RBAC**: 
  - `viewer`: Can see lists and details (e.g. `order_doc_title`).
  - `operator`: Can see action buttons (e.g. `btn_create_new`, `action_edit`, `action_delete`). Elements requiring operator access are conditionally rendered wrapped in `{% if current_user.role == 'operator' %}` or via the `@operator_required` decorator.

## Core Page Contracts

### 1. Unified List Pages
Applies to: **Fabric List**, **Sample List**, **Order List**, **Production Dashboard**, **Wash Queue**, **Wash History**.

- **Purpose**: Display a searchable/filterable list of items.
- **UI Blueprint**: Uses `ui_list_page()` macro (`src/hopaoems/templates/macros/ui/layouts.html`).
- **Layout Zones**:
  1. **Header (KPIs & Title)**: Uses `ui_kpi_card()` or a title string. `ui_page_header_with_badge` for counts.
  2. **Toolbar**: `ui_toolbar()` containing:
     - Search / Filters (left).
     - Action buttons (right) like `btn_export`, `btn_create_new`.
  3. **Data Table**: Uses `ui_table()`. Columns are styled for single-line constraints except for specific note columns.
- **Actions**: Clicking a row views details. "New" button redirects to form.

### 2. Entity View Pages
Applies to: **Order View**, **Sample View**, **Wash Session View**, **Production Task View**.

- **Purpose**: Show granular read-only details of a specific record. Single scrollable view.
- **UI Blueprint**: Custom grid layouts using `ui_stack()` and `ui_card()`.
- **Layout Zones**:
  1. **Title / Back button**: Breadcrumbs or back link.
  2. **Main Property Grid**: Key-value pairs using `ui_property_item()`.
  3. **Relational Data**: Sub-tables (e.g. Order Items, Roll History, Production Logs).
- **Actions**: "Edit", "Delete" (Operator-only) usually placed at the top or bottom right.

### 3. Creation / Edit Forms
Applies to: **Fabric Form**, **Sample Form**, **Order Form**, **Production Form**, Models/Modals.

- **Purpose**: Mutate entity data.
- **RBAC**: Strictly `@operator_required`.
- **UI Blueprint**: Uses `ui_form_layout()` macro to divide fields logically.
- **Layout Zones**:
  1. **Form Header**: `title` and `.form-header`.
  2. **Field Grid**: 2-column or 1-column responsive grid.
  3. **Dynamic Lists**: (e.g. Adding multiple order items dynamically via JS).
  4. **Footer Actions**: Uses `ui_form_actions()` (Cancel / Submit).

### 4. Specialized Action Views
- **Fabric Explorer**: Visual grid card view (`ui_card`) with thumbnails and color swatches. Heavy JS interactions.
- **Fabric Stock-In**: Specialized matrix grid for entering multiple roll dimensions via keyboard-friendly inputs (Excel-like). Includes XLS import logic.
- **Sample Color Picker**: Heavy JS + Canvas interacting with image coordinates to save Lab/RGB measurements to `sample_color_map`.

## Form Component Macros
- `ui_input_field(name, label, value, ...)`
- `ui_textarea_field(...)`
- `ui_select_field(...)`
All forms leverage these macros for standardized spacing, styling, and unified i18n support. Raw `<input>` tags are disallowed unless custom JS components (like the color picker) demand it.
