
import json
import os

def fix_file(path):
    print(f"Fixing {path}...")
    try:
        with open(path, 'r', encoding='utf-8-sig') as f: # Handle BOM
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load with utf-8-sig: {e}")
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e2:
            print(f"Failed to load with utf-8: {e2}")
            return

    # Add keys if missing
    if "common.view_mode.grid" not in data:
        data["common.view_mode.grid"] = "Grid View" if "en" in path else "Chế độ Lưới"
    if "common.view_mode.table" not in data:
        data["common.view_mode.table"] = "Table View" if "en" in path else ("Chế độ Bảng" if "vi" in path else "表格檢視")

    # Remove duplicates? Python dict handles it automatically.

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {path}")

fix_file('src/hopaoems/i18n/seed.en.json')
fix_file('src/hopaoems/i18n/seed.vi.json')
fix_file('src/hopaoems/i18n/seed.zh-TW.json')
