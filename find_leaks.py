import json
import os

i18n_path = 'src/hopaoems/i18n'
for lang in ['en', 'zh-TW', 'vi']:
    path = os.path.join(i18n_path, f'seed.{lang}.json')
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            leaks = [k for k, v in data.items() if k == v and '.' in k]
            if leaks:
                print(f"--- {lang} Leaks ({len(leaks)}) ---")
                for l in sorted(leaks):
                    print(l)
