
import json
import os
import sys

def verify_i18n_keys():
    """Verify that all 3 seed files have identical key sets."""
    base_path = os.path.join('src', 'hopaoems', 'i18n')
    langs = ['en', 'zh-TW', 'vi']
    
    seeds = {}
    for lang in langs:
        path = os.path.join(base_path, f'seed.{lang}.json')
        if not os.path.exists(path):
            print(f"FAIL: Missing seed file for {lang}")
            sys.exit(1)
        with open(path, 'r', encoding='utf-8') as f:
            seeds[lang] = json.load(f)
            
    # Flatten keys? The seeds are likely flat key-value pairs per contract (dot notation keys).
    # If nested, we need to flatten. Assuming flat for now based on previous i18n service code using get(key).
    
    keys_en = set(seeds['en'].keys())
    keys_zh = set(seeds['zh-TW'].keys())
    keys_vi = set(seeds['vi'].keys())
    
    all_keys = keys_en | keys_zh | keys_vi
    
    violations = []
    
    # Check completeness
    missing_en = all_keys - keys_en
    missing_zh = all_keys - keys_zh
    missing_vi = all_keys - keys_vi
    
    if missing_en: violations.append(f"EN Missing: {missing_en}")
    if missing_zh: violations.append(f"ZH-TW Missing: {missing_zh}")
    if missing_vi: violations.append(f"VI Missing: {missing_vi}")
    
    if violations:
        print("\n".join(violations))
        sys.exit(1)
        
    print("I18N CONTRACT PASSED")

if __name__ == '__main__':
    verify_i18n_keys()
