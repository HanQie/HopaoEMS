import json
import os

def check_parity():
    langs = ['en', 'zh-TW', 'vi']
    data = {}
    for lang in langs:
        path = f'src/hopaoems/i18n/seed.{lang}.json'
        with open(path, 'r', encoding='utf-8') as f:
            data[lang] = set(json.load(f).keys())
    
    all_keys = data['en'] | data['zh-TW'] | data['vi']
    
    for lang in langs:
        missing = all_keys - data[lang]
        print(f"--- {lang} Missing ({len(missing)}) ---")
        for k in sorted(list(missing)):
            print(k)

if __name__ == "__main__":
    check_parity()
