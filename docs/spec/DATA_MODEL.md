# Data Model

This document outlines the SQLite database schema and domain invariants for the application, based on `src/hopaoems/services/schema_migrations.py`.

## Core Entities & Relationships

### 1. Users (`users`)
- **Fields**: `id`, `username`, `password_hash`, `role`, `created_at`
- **Invariants**: 
  - `username` must be UNIQUE.
  - `role` must be either `'operator'` or `'viewer'`. (Legacy `'admin'` roles are migrated to `'operator'`).

### 2. Fabrics (`fabrics`)
- **Fields**: `id`, `fabric_code`, `material`, `width_cm`, `width_mm`, `yard_weight_gyd`, `remark`, `created_at`
- **Invariants**: 
  - `fabric_code` must be UNIQUE.

### 3. Cylinders (`cylinders`)
- **Fields**: `id`, `fabric_id` (FK), `cylinder_no`, `created_at`
- **Relationships**: Belongs to `fabrics`.

### 4. Rolls (`rolls`)
- **Fields**: `id`, `cylinder_id` (FK), `roll_no`, `length_m`, `weight_kg`, `status`, `remark`, `created_at`, `updated_at`
- **Invariants**:
  - `(cylinder_id, roll_no)` must be UNIQUE (enforced by `idx_rolls_cylinder_roll`).
  - Expected `status` enum: `in_stock`, `depleted`, etc.
- **Relationships**: Belongs to `cylinders`.

### 5. Roll History (`roll_history`)
- **Fields**: `id`, `roll_id` (FK), `action`, `old_qty`, `new_qty`, `delta`, `source`, `note`, `created_by`, `created_at`
- **Relationships**: Tracks all lifecycle events for a `rolls` record.

### 6. Samples (`samples`)
- **Fields**: `id`, `sample_no`, `title`, `remark`, `fabric_no`, `sales_code`, `version`, `date_received`, asset metadata (`source_filename`, `source_mime`, `source_path`, `preview_path`, `preview_mime`, `preview_size`), printing configs (`printing_environment`, `printing_file_name`), `created_at`
- **Invariants**:
  - `sample_no` must be UNIQUE.

### 7. Sample Color Map (`sample_color_map`)
- **Fields**: `id`, `sample_id` (FK), pick coordinates (`pick_x`, `pick_y`), RGB colors (`rgb_r`, `rgb_g`, `rgb_b`, `hex`), target lab values (`target_mode`, `target_l`, `target_a`, `target_b`), notes (`note`, `target_note`), `created_at`
- **Relationships**: Belongs to `samples`.

### 8. Inks (`inks`)
- **Fields**: `id`, `date`, `type`, `color`, `qty`, `note`, `created_at`

### 9. Orders (`orders`)
- **Fields**: `id`, `order_no`, `received_date`, `due_date`, `status`, `note`, `created_at`, `updated_at`
- **Invariants**:
  - `order_no` must be UNIQUE.

### 10. Order Items (`order_items`)
- **Fields**: `id`, `order_id` (FK), `fabric_no`, `sample_id` (FK), `qty`, `note`
- **Relationships**: Belongs to `orders` and references `samples`.

### 11. Production Tasks (`production_tasks`)
- **Fields**: `id`, `order_id` (FK), `order_item_id` (FK), `sample_id` (FK), `fabric_no`, `target_qty`, `used_length`, `status`, `note`, `created_at`, `updated_at`
- **Invariants**:
  - `order_item_id` must be UNIQUE (1:1 mapping with `order_items`).
- **Relationships**: References `orders` and `samples`.

### 12. Production Logs (`production_logs`)
- **Fields**: `id`, `task_id` (FK), `roll_id` (FK), `length`, `note`, `roll_depleted`, `washed_at`, `wash_session_id` (FK), `operator_id` (FK), `status`, `created_at`, `updated_at`
- **Relationships**: Links `production_tasks` with specific `rolls` consumed. Points to standard `users` for the operator. Tracks washing status up to `wash_sessions`.

### 13. Wash Sessions (`wash_sessions`)
- **Fields**: `id`, `vat_code`, `roll_count`, `total_length`, `operator_id` (FK), `created_at`
- **Relationships**: Collects multiple `production_logs` during a wash session.

### 14. Audit Logs (`audit_logs`)
- **Fields**: `id`, `operator_id` (FK), `action`, `target_entity`, `target_id`, `timestamp`, `details`
- **Relationships**: System-wide changes tracking pointing to `users`.

## Key Cross-Domain Invariants
- **Authentication**: All modifying operations require a valid user. `viewer` role provides read-only access (with some functional views limited to operators, notably creation/edit forms).
- **Deletion Rules**: Mostly soft-deletes or status updates instead of hard deletion (e.g., fabrics depletion, order status changes).
- **Roll Consumption**: `production_logs` records fabric length consumed. The related `rolls.length_m` is adjusted, and an entry is placed in `roll_history`.
- **Foreign Key Constraints**: Standard SQLite PRAGMA foreign keys are assumed to ensure referential integrity, particularly on deleting users, orders, or samples.
