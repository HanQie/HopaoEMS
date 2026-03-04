import json
import os

patches = {
    "zh-TW": {
        "production.produce.fields.printed_length": "印刷長度",
        "production.logs.length": "長度",
        "production.table.length": "長度",
        "production.fields.task_info": "任務資訊",
        "production.table.task_info": "任務資訊",
        "production.status.unwashed": "待水洗",
        "production.form.subtitle": "登記任務的生產狀態與進度",
        "production.quick.subtitle": "登記任務的生產狀態與進度"
    },
    "vi": {
        "production.produce.fields.printed_length": "Chiều dài in",
        "production.logs.length": "Chiều dài",
        "production.table.length": "Chiều dài",
        "production.fields.task_info": "Thông tin nhiệm vụ",
        "production.table.task_info": "Thông tin nhiệm vụ",
        "production.status.unwashed": "Chưa giặt",
        "production.form.subtitle": "Đăng ký trạng thái sản xuất",
        "production.quick.subtitle": "Đăng ký trạng thái sản xuất"
    },
    "en": {
        "production.produce.fields.printed_length": "Printed Length",
        "production.logs.length": "Length",
        "production.table.length": "Length",
        "production.fields.task_info": "Task Info",
        "production.table.task_info": "Task Info",
        "production.status.unwashed": "Unwashed",
        "production.form.subtitle": "Register print job details",
        "production.quick.subtitle": "Register print job details"
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
