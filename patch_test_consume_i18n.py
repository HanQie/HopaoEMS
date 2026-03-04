import json
import os

patches = {
    "en": {
        "production.action.test_consume": "Test Consume",
        "production.test_consume.title": "Test Consume",
        "production.test_consume.desc": "Quickly consume fabric roll length without binding to a task.",
        "production.test_consume.fields.search_roll": "Search Roll",
        "production.test_consume.fields.roll": "Target Roll",
        "production.test_consume.fields.roll_help": "Select a roll to test consume from.",
        "production.test_consume.fields.no_rolls_hint": "No in-stock rolls found matching your search.",
        "production.test_consume.fields.length": "Consume Length",
        "production.test_consume.fields.note": "Note",
        "production.test_consume.fields.mark_empty": "Mark roll as empty (depleted)",
        "production.test_consume.success": "Test consume recorded successfully.",
        "production.error.missing_fields": "Required fields are missing.",
        "production.error.invalid_length": "Invalid consume length."
    },
    "zh-TW": {
        "production.action.test_consume": "測試領用",
        "production.test_consume.title": "測試領用",
        "production.test_consume.desc": "快速消耗布疋長度，不綁定特定生產任務。",
        "production.test_consume.fields.search_roll": "搜尋布疋",
        "production.test_consume.fields.roll": "目標布疋",
        "production.test_consume.fields.roll_help": "選擇要測試領用的布疋。",
        "production.test_consume.fields.no_rolls_hint": "找不到符合條件的在庫布疋。",
        "production.test_consume.fields.length": "領用長度",
        "production.test_consume.fields.note": "備註",
        "production.test_consume.fields.mark_empty": "標記為空（已用盡）",
        "production.test_consume.success": "測試領用紀錄已成功新增。",
        "production.error.missing_fields": "必要欄位缺失。",
        "production.error.invalid_length": "領用長度無效。"
    },
    "vi": {
        "production.action.test_consume": "Tiêu hao thử nghiệm",
        "production.test_consume.title": "Tiêu hao thử nghiệm",
        "production.test_consume.desc": "Nhanh chóng tiêu hao chiều dài cuộn vải mà không gắn với nhiệm vụ nào.",
        "production.test_consume.fields.search_roll": "Tìm kiếm cuộn",
        "production.test_consume.fields.roll": "Cuộn đích",
        "production.test_consume.fields.roll_help": "Chọn cuộn để tiêu hao thử nghiệm.",
        "production.test_consume.fields.no_rolls_hint": "Không tìm thấy cuộn nào trong kho phù hợp.",
        "production.test_consume.fields.length": "Chiều dài tiêu hao",
        "production.test_consume.fields.note": "Ghi chú",
        "production.test_consume.fields.mark_empty": "Đánh dấu cuộn đã hết",
        "production.test_consume.success": "Đã ghi nhận tiêu hao thử nghiệm thành công.",
        "production.error.missing_fields": "Thiếu các trường bắt buộc.",
        "production.error.invalid_length": "Chiều dài tiêu hao không hợp lệ."
    }
}

base_dir = "src/hopaoems/i18n"
for lang, new_keys in patches.items():
    path = os.path.join(base_dir, f"seed.{lang}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for k, v in new_keys.items():
            data[k] = v  # Add or overwrite
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Patched {path}")
    else:
        print(f"WARN: {path} not found")
print("Done.")
