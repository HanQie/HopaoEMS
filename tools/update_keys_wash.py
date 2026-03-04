import json
import os

keys = {
    "wash.pending.title": { "en": "Pending Wash", "zh-TW": "待洗缸清單", "vi": "Chờ giặt" },
    "wash.history.title": { "en": "Wash History", "zh-TW": "水洗歷史", "vi": "Lịch sử giặt" },
    "wash.summary.rolls": { "en": "Rolls", "zh-TW": "疋數", "vi": "Cuộn" },
    "wash.summary.logs": { "en": "Logs", "zh-TW": "筆數", "vi": "Logs" },
    "wash.summary.total_length": { "en": "Total", "zh-TW": "總長", "vi": "Tổng" },
    "wash.action.mark_washed": { "en": "Mark Washed", "zh-TW": "確認水洗", "vi": "Xác nhận giặt" },
    "wash.action.revoke": { "en": "Revoke", "zh-TW": "撤銷", "vi": "Thu hồi" },
    "wash.session.label": { "en": "Wash Session", "zh-TW": "洗程", "vi": "Phiên giặt" },
    "production.action.go_wash": { "en": "Wash", "zh-TW": "去水洗", "vi": "Giặt" },
    "production.action.view_wash_history": { "en": "Wash History", "zh-TW": "檢視紀錄", "vi": "Xem lịch sử" },
    "wash.hint.history_scoped": { "en": "Showing sessions for active tasks only", "zh-TW": "僅顯示未完成任務之洗程", "vi": "Chỉ hiển thị phiên cho nhiệm vụ đang hoạt động" },
    "wash.success.revoked": { "en": "Session revoked", "zh-TW": "洗程已撤銷", "vi": "Đã thu hồi phiên" },
    "wash.confirm.revoke_message": { "en": "Revoke this session? Logs will return to pending.", "zh-TW": "確定撤銷此洗程？紀錄將回到待洗清單。", "vi": "Thu hồi phiên này? Logs sẽ quay lại chờ giặt." },
    "wash.success.sessions_created": { "en": "{count} sessions created", "zh-TW": "已建立 {count} 筆洗程", "vi": "Đã tạo {count} phiên" }
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
        data = dict(sorted(data.items()))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Updated {fname}")
    else:
        print(f"No changes for {fname}")
