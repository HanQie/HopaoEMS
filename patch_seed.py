# -*- coding: utf-8 -*-
import json
import os

paths = {
    'en': 'src/hopaoems/i18n/seed.en.json',
    'zh-TW': 'src/hopaoems/i18n/seed.zh-TW.json',
    'vi': 'src/hopaoems/i18n/seed.vi.json'
}

additions = {
    'en': {
        'common.clear': 'Clear',
        'wash.history.empty.no_results': 'No sessions match your search.',
        'wash.history.empty.try_other_query': 'Try adjusting your search query.',
        'wash.history.empty.no_sessions': 'No active wash sessions.',
        'production.quick_produce.printed_ratio': 'Printed {printed} / {target} · {pct}%'
    },
    'zh-TW': {
        'common.clear': '清除',
        'wash.history.empty.no_results': '找不到符合搜尋條件的水洗紀錄。',
        'wash.history.empty.try_other_query': '請嘗試不同的關鍵字。',
        'wash.history.empty.no_sessions': '目前沒有待處理的水洗紀錄。',
        'production.quick_produce.printed_ratio': '已印 {printed} / {target} · {pct}%'
    },
    'vi': {
        'common.clear': 'Xóa',
        'wash.history.empty.no_results': 'Không tìm thấy phiên giặt nào phù hợp với tìm kiếm.',
        'wash.history.empty.try_other_query': 'Vui lòng thử điều chỉnh từ khóa tìm kiếm.',
        'wash.history.empty.no_sessions': 'Hiện không có ghi chép giặt nào đang chờ xử lý.',
        'production.quick_produce.printed_ratio': 'Đã in {printed} / {target} · {pct}%'
    }
}

for lang, filepath in paths.items():
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        updated = False
        for key, value in additions[lang].items():
            # Force update to make sure it's accurate
            data[key] = value
            updated = True
                
        if updated:
            # Sort the dictionary and save
            sorted_data = dict(sorted(data.items(), key=lambda t: t[0] if t[0] != '__sources__' else ''))
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(sorted_data, f, indent=2, ensure_ascii=False)
            print(f'Patched {lang} successfully')
    else:
        print(f'File {filepath} not found')
