# HopaoEMS Domain Contract (Single Source of Truth)

## Specifications
> [!IMPORTANT]
> Field naming is canonical. Repos must not introduce aliases in DB schema; compatibility must be handled in repo read/write mapping only.

## Tables & Schema

### 1. auth
| Table | Column | Type | Constraints |
|---|---|---|---|
| `users` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `username` | TEXT | CHECK(length > 0) UNIQUE |
| | `password_hash` | TEXT | NOT NULL |
| | `role` | TEXT | CHECK(role IN ('viewer', 'operator')) |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |

### 2. fabric (Fabric > Cylinder > Roll)
| Table | Column | Type | Constraints |
|---|---|---|---|
| `fabrics` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `fabric_code` | TEXT | UNIQUE NOT NULL |
| | `material` | TEXT | |
| | `width_cm` | REAL | |
| | `yard_weight_gyd` | REAL | |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| `cylinders` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `fabric_id` | INTEGER | FOREIGN KEY REFERENCES fabrics(id) |
| | `cylinder_no` | TEXT | NOT NULL |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| `rolls` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `cylinder_id` | INTEGER | FOREIGN KEY REFERENCES cylinders(id) |
| | `roll_no` | TEXT | NOT NULL |
| | `length_m` | REAL | NOT NULL |
| | `weight_kg` | REAL | |
| | `status` | TEXT | DEFAULT 'in_stock' CHECK(status IN ('in_stock', 'depleted')) |
| | `remark` | TEXT | |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| `roll_history` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `roll_id` | INTEGER | FOREIGN KEY REFERENCES rolls(id) |
| | `action` | TEXT | CHECK(action IN ('inbound', 'depleted', 'manual_adjust', 'test_use', 'test_consume')) |
| | `old_qty` | REAL | |
| | `new_qty` | REAL | |
| | `delta` | REAL | |
| | `source` | TEXT | |
| | `note` | TEXT | |
| | `created_by` | TEXT | |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |

### 3. sample
| Table | Column | Type | Constraints |
|---|---|---|---|
| `samples` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `sample_no` | TEXT | UNIQUE NOT NULL |
| | `title` | TEXT | NOT NULL |
| | `remark` | TEXT | |
| | `fabric_no` | TEXT | |
| | `name` | TEXT | |
| | `sales_code` | TEXT | |
| | `version` | TEXT | |
| | `date_received` | TEXT | |
| | `printing_environment` | TEXT | |
| | `printing_file_name` | TEXT | |
| | `source_filename` | TEXT | |
| | `source_mime` | TEXT | |
| | `source_path` | TEXT | |
| | `preview_path` | TEXT | |
| | `preview_mime` | TEXT | |
| | `preview_size` | INTEGER | |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| `sample_color_map` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `sample_id` | INTEGER | FOREIGN KEY REFERENCES samples(id) |
| | `pick_x` | INTEGER | |
| | `pick_y` | INTEGER | |
| | `rgb_r` | INTEGER | |
| | `rgb_g` | INTEGER | |
| | `rgb_b` | INTEGER | |
| | `hex` | TEXT | |
| | `target_mode` | TEXT | CHECK(target_mode IN ('lab', 'note')) |
| | `target_l` | REAL | |
| | `target_a` | REAL | |
| | `target_b` | REAL | |
| | `target_note` | TEXT | |
| | `note` | TEXT | |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |

### 4. ink
| Table | Column | Type | Constraints |
|---|---|---|---|
| `inks` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `date` | TEXT | NOT NULL |
| | `type` | TEXT | NOT NULL |
| | `color` | TEXT | NOT NULL |
| | `qty` | REAL | NOT NULL |
| | `note` | TEXT | |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |

### 5. order
| Table | Column | Type | Constraints |
|---|---|---|---|
| `orders` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `order_no` | TEXT | UNIQUE NOT NULL |
| | `received_date` | TEXT | |
| | `due_date` | TEXT | |
| | `status` | TEXT | DEFAULT 'open' CHECK(status IN ('open', 'closed')) |
| | `note` | TEXT | |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| | `updated_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| `order_items` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `order_id` | INTEGER | FOREIGN KEY REFERENCES orders(id) |
| | `fabric_no` | TEXT | NOT NULL |
| | `sample_id` | INTEGER | FOREIGN KEY REFERENCES samples(id) |
| | `qty` | REAL | NOT NULL |
| | `note` | TEXT | |

### 6. production
| Table | Column | Type | Constraints |
|---|---|---|---|
| `production_tasks` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `order_id` | INTEGER | FOREIGN KEY REFERENCES orders(id) |
| | `fabric_no` | TEXT | NOT NULL |
| | `sample_id` | INTEGER | FOREIGN KEY REFERENCES samples(id) |
| | `target_qty` | REAL | NOT NULL |
| | `note` | TEXT | |
| | `status` | TEXT | DEFAULT 'printing' CHECK(status IN ('printing', 'done', 'canceled')) |
| | `used_length` | REAL | DEFAULT 0 |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| | `updated_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| `production_logs` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `task_id` | INTEGER | FOREIGN KEY REFERENCES production_tasks(id) |
| | `roll_id` | INTEGER | FOREIGN KEY REFERENCES rolls(id) |
| | `length` | REAL | NOT NULL |
| | `note` | TEXT | |
| | `roll_depleted` | INTEGER | DEFAULT 0 |
| | `washed_at` | TEXT | NULLABLE |
| | `wash_session_id` | INTEGER | FOREIGN KEY REFERENCES wash_sessions(id) |
| | `operator_id` | INTEGER | FOREIGN KEY REFERENCES users(id) |
| | `status` | TEXT | DEFAULT 'unwashed' |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |
| | `updated_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |

### 7. wash
| Table | Column | Type | Constraints |
|---|---|---|---|
| `wash_sessions` | `id` | INTEGER | PRIMARY KEY AUTOINCREMENT |
| | `vat_code` | TEXT | NOT NULL |
| | `roll_count` | INTEGER | NOT NULL |
| | `total_length` | REAL | NOT NULL |
| | `operator_id` | INTEGER | FOREIGN KEY REFERENCES users(id) NULLABLE |
| | `created_at` | TEXT | DEFAULT CURRENT_TIMESTAMP |

> [!NOTE]
> `test_consume` in `roll_history` is used for testing consumption (e.g., sample testing). It MUST NOT create a `production_logs` entry and MUST NOT appear in the wash list.
