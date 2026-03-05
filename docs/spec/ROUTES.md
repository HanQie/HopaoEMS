# Route Contract

This document outlines the enforced routing structure of the application based on `src/hopaoems/blueprints/*.py` and the `routes_contract.json`. 

## Core Principles
1. **Namespaces**: Routes are grouped by entity (`/fabric/`, `/sample/`, `/order/`, `/production/`, `/wash/`, `/ink/`).
2. **Access Control (RBAC)**: 
   - `viewer` role can access all `GET` views for listing and details.
   - `operator` role is required for `POST`, `/new`, `/edit`, `/delete`, and all mutative actions.
   - Exceptions: Login/Logout do not require a login.
3. **Template Mapping**: `ui_*` blueprints map directly to `templates/<entity>/<action>.html`. For instance, `ui_fabric.fabric_list` renders `fabric/list.html`.

## Endpoints

### Auth (`auth.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/auth/login` | `GET`, `POST` | Public | `auth/login.html` | `username`, `password` |
| `/auth/logout` | `POST` | Auth | Redirects to `/auth/login` | |

### Main (`ui_main.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/` | `GET` | All | `dashboard.html` | Dashboard metrics |
| `/i18n/set/<lang>` | `GET` | Public | Set session language | `lang` |

### Fabric (`ui_fabric.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/fabric/` | `GET` | All | `fabric/list.html` | Filters (`q`, `m`, etc.) |
| `/fabric/explorer` | `GET` | All | `fabric/explorer.html` | |
| `/fabric/new` | `GET`, `POST` | Operator | `fabric/form.html` | Fabric data |
| `/fabric/<id>/edit` | `GET`, `POST` | Operator | `fabric/form.html` | Fabric data |
| `/fabric/stock-in` | `GET` | Operator | `fabric/stock_in.html` | Excel/Form entry |
| `/fabric/stock-in/commit` | `POST` | Operator | Bulk insert rolls | JSON payload |
| `/fabric/stock-in/template.xlsx`| `GET` | Operator | Serves blank Excel | |
| `/fabric/stock-in/import-xlsx`| `POST` | Operator | Parses Excel to JSON | `file` |
| `/fabric/roll/<id>/adjust-stock`| `GET`, `POST` | Operator | Modal or Form | `new_length`, `reason`|
| `/fabric/roll/<id>/history`| `GET` | All | `fabric/components/roll_history.html` | |
| `/fabric/roll/<id>/edit` | `GET`, `POST` | Operator | `fabric/roll_form.html` | |
| `/fabric/roll/<id>/delete` | `POST` | Operator | Soft-deletes roll | |
| `/fabric/cylinder/<id>/edit` | `GET`, `POST` | Operator | `fabric/cylinder_form.html`| |
| `/fabric/cylinder/<id>/delete`| `POST` | Operator | | |

### Sample (`ui_sample.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/sample/` | `GET` | All | `sample/list.html` | Filters |
| `/sample/new` | `GET`, `POST` | Operator | `sample/form.html` | Form data, image upload |
| `/sample/<id>` | `GET` | All | `sample/view.html` | |
| `/sample/<id>/edit` | `GET`, `POST` | Operator | `sample/form.html` | Form data, image upload |
| `/sample/<id>/delete` | `POST` | Operator | Deletes sample | |
| `/sample/<id>/pick-color`| `POST` | Operator | JSON save colors | `colors` |
| `/sample/<id>/color-corrections/save`| `POST`| Operator | JSON save lab inputs | |

### Order (`ui_order.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/order/` | `GET` | All | `order/list.html` | Filters |
| `/order/new` | `GET`, `POST` | Operator | `order/form.html` | Items dict |
| `/order/<id>` | `GET` | All | `order/view.html` | |
| `/order/<id>/edit` | `GET`, `POST` | Operator | `order/form.html` | Items dict |
| `/order/<id>/delete` | `POST` | Operator | Soft-deletes order | |
| `/order/task/<task_id>/reopen`| `POST` | Operator | Reopens production | |
| `/order/item/<item_id>/delete`| `POST` | Operator | Removes item | |

### Production (`ui_production.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/production/` | `GET` | All | `production/dashboard.html` | |
| `/production/task/<id>` | `GET` | All | `production/task_view.html`| |
| `/production/task/<id>/produce`| `GET`, `POST`| Operator| `production/task_produce.html`| `roll_id`, `length`, `note`|
| `/production/task/<id>/done` | `POST` | Operator | Marks task done | |
| `/production/log/<id>/edit` | `GET`, `POST` | Operator | `production/log_form.html` | |
| `/production/log/<id>/delete`| `POST` | Operator | Reverts task length | |
| `/production/log/<id>/undo-wash`| `POST` | Operator| Removes from session | |

### Wash (`ui_wash.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/wash/` | `GET` | All | `wash/list.html` | Unwashed logs list |
| `/wash/history` | `GET` | All | `wash/history.html` | Sessions list |
| `/wash/session/<id>` | `GET` | All | `wash/session_view.html` | |
| `/wash/register/<vat_code>` | `GET` | Operator | `wash/register.html` | |
| `/wash/commit` | `POST` | Operator | Creates wash session | `vat_code`, `log_ids` |
| `/wash/revoke/<session_id>` | `POST` | Operator | Rolls back session | |

### Settings & Admin (`ui_settings.py`)
| Path | Method | Roles | Template / Action | Parameters |
|:---|:---:|:---:|:---|:---|
| `/settings/` | `GET` | Admin | `settings/settings.html` | |
| `/settings/activity` | `GET` | Admin | `settings/activity.html`| |

## Debug Endpoints
(Available in `development` mode or locally)
- `/__debug/build`
- `/__debug/i18n`
- `/__debug/whoami`
