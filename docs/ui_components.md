# UI Component Contract

This document defines the interface and visual standards for the HopaoEMS UI macros. Templates must adhere to these contracts and avoid raw styling or direct Tailwind tokens whenever possible.

## 1. Statistics Cards

### `C.ui_stat_card`
Standard OS-style card for displaying a single metric or status.

**Parameters:**
- `label` (String): The title/label of the metric.
- `value` (String/Any, Optional): The primary value to display.
- `hint` (String, Optional): Secondary subtext displayed below the value.
- `tone` (Enum, Default: `'neutral'`): Visual accent color.
- `u_props` (String, Optional): Safe-pass attributes for accessibility/data-hooks.

**Tone Enum:**
- `neutral`: Slate border (Default).
- `success`: Emerald accent.
- `warning`: Amber accent.
- `danger`: Rose accent.
- `info`: Blue accent.

**Advanced Usage:**
Supports a `caller()` block for rendering complex content in the value slot (e.g., status badges).

---

### `C.ui_stat_grid`
Helper macro to arrange multiple statistics cards in a responsive grid.

**Parameters:**
- `items` (List[Dict]): List of card configurations. Each dict supports `label`, `value`, `hint`, and `tone`.
- `cols` (Enum: `2 | 3 | 4`, Default: `4`): Number of columns on small screens and above.

---

## 2. Status Badges

### `C.ui_status_badge`
Smart badge which maps domain-specific statuses to appropriate visual tones and labels.

**Parameters:**
- `kind` (Enum: `'wash' | 'roll' | 'order' | 'task'`): The domain of the status.
- `value` (String): The raw status value (e.g., `'washed'`, `'in_stock'`).
- `ts` (String, Optional): Timestamp to display alongside the badge.

---

## 3. General Visual Tokens (Tone Guard)

All components using the `tone` parameter strictly adhere to the following semantic mapping. Invalid tones will automatically fallback to `neutral`.

| Tone | Context | Visual Mapping |
| :--- | :--- | :--- |
| `neutral` | Default, Secondary | Slate / Gray |
| `success` | Positive, Completed, In-stock | Emerald / Green |
| `warning` | Caution, Pending, Unwashed | Amber / Orange |
| `danger` | Critical, Error, Depleted | Rose / Red |
| `info` | Informational, In-progress | Blue |

**Stability Contract:**
Templates must NOT pass raw Tailwind classes through `kwargs` to override these tones. Visual consistency is enforced at the macro level.
