import json
import os

keys = {
    "production.task.printing_file_name": {
        "en": "Printing File",
        "zh-TW": "印花檔案",
        "vi": "Tập tin in"
    },
    "production.task.sample_version": {
        "en": "Version",
        "zh-TW": "版本",
        "vi": "Phiên bản"
    },
    "production.quick_produce.roll_picker.title": {
        "en": "Roll Selection",
        "zh-TW": "選擇疋號",
        "vi": "Chọn cuộn vải"
    },
    "production.quick_produce.roll_picker.cyl_filter_placeholder": {
        "en": "Filter Cylinder...",
        "zh-TW": "輸入缸號前綴...",
        "vi": "Lọc mã trục..."
    },
    "production.quick_produce.roll_picker.search_placeholder": {
        "en": "Search Roll or Batch...",
        "zh-TW": "搜尋疋號或批次...",
        "vi": "Tìm cuộn vải..."
    },
    "production.quick_produce.roll_picker.selected_prefix": {
        "en": "Selected:",
        "zh-TW": "已選：",
        "vi": "Đã chọn:"
    },
    "production.quick_produce.roll_picker.empty_hint": {
        "en": "No roll selected",
        "zh-TW": "尚未選擇",
        "vi": "Chưa chọn cuộn"
    }
}

base_dir = r"c:\Users\JingHu\Desktop\hopaoems2\src\hopaoems\i18n"
files = ["seed.en.json", "seed.zh-TW.json", "seed.vi.json"]
langs = ["en", "zh-TW", "vi"]

for fname, lang in zip(files, langs):
    path = os.path.join(base_dir, fname)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    updated = False
    for k, v_map in keys.items():
        if k not in data:
            data[k] = v_map[lang]
            updated = True
    
    if updated:
        # Sort keys
        data = dict(sorted(data.items()))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Updated {fname}")
    else:
        print(f"No changes for {fname}")
