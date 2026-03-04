"""
Script to add Phase 6 Production i18n keys to all seed files.
Keys cover: production table headers, progress bar, action labels, aria label, and server-side error.
"""
import json
import os

langs_keys = {
    "en": {
        "production.fields.task_info": "Task Info",
        "production.progress.title": "Progress",
        "production.progress.aria_label": "Production progress",
        "production.action.produce": "Quick Produce",
        "production.action.complete": "Complete",
        "production.action.view": "View",
        "production.error.unwashed_blocks_complete": "Cannot complete: {count} log(s) have not been washed yet."
    },
    "zh-TW": {
        "production.fields.task_info": "任務資訊",
        "production.progress.title": "進度",
        "production.progress.aria_label": "生產進度",
        "production.action.produce": "快速生產",
        "production.action.complete": "完成",
        "production.action.view": "檢視",
        "production.error.unwashed_blocks_complete": "無法完成：尚有 {count} 筆日誌未水洗。"
    },
    "vi": {
        "production.fields.task_info": "Thông tin nhiệm vụ",
        "production.progress.title": "Tiến độ",
        "production.progress.aria_label": "Tiến độ sản xuất",
        "production.action.produce": "Sản xuất nhanh",
        "production.action.complete": "Hoàn thành",
        "production.action.view": "Xem",
        "production.error.unwashed_blocks_complete": "Không thể hoàn thành: {count} nhật ký chưa được giặt."
    }
}

base_dir = "src/hopaoems/i18n"
for lang, new_keys in langs_keys.items():
    path = os.path.join(base_dir, f"seed.{lang}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in new_keys.items():
            if k not in data:
                data[k] = v
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Updated {path}")
    else:
        print(f"WARN: {path} not found")
print("Done.")
