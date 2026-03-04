import json
import os

patches = {
    "zh-TW": {
        "production.task.title": "任務詳情",
        "production.task.info": "任務資訊"
    },
    "vi": {
        "production.task.title": "Chi tiết nhiệm vụ",
        "production.task.info": "Thông tin nhiệm vụ"
    },
    "en": {
        "production.task.title": "Task Detail",
        "production.task.info": "Task Info"
    }
}

base_dir = "src/hopaoems/i18n"
for lang, new_keys in patches.items():
    path = os.path.join(base_dir, f"seed.{lang}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in new_keys.items():
            data[k] = v  # Force overwrite
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Patched {path}")
    else:
        print(f"WARN: {path} not found")
print("Done.")
