import json
import os

files = {
    'src/hopaoems/i18n/seed.en.json': {
        "sample.search.placeholder": "Search sample no or title...",
        "sample.section.adjustments": "Adjustments / Selections",
        "common.show": "Show",
        "common.hide": "Hide"
    },
    'src/hopaoems/i18n/seed.zh-TW.json': {
        "sample.search.placeholder": "搜尋樣品編號或名稱...",
        "sample.section.adjustments": "調整 / 選項",
        "common.show": "顯示",
        "common.hide": "隱藏"
    },
    'src/hopaoems/i18n/seed.vi.json': {
        "sample.search.placeholder": "Tìm kiếm mã mẫu hoặc tên...",
        "sample.section.adjustments": "Điều chỉnh / Lựa chọn",
        "common.show": "Hiện",
        "common.hide": "Ẩn"
    }
}

for path, new_keys in files.items():
    if not os.path.exists(path): continue
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    data.update(new_keys)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=True)
    print(f"Updated {path}")
