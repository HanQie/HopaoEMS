import os
import sys

def main():
    print("GATE: VAT GROUPING APPLIED CONTRACT")
    
    # 1. Check Data Source (Repo)
    repo_path = "src/hopaoems/services/wash_repo.py"
    if not os.path.exists(repo_path):
        print(f"  [FAIL] {repo_path} missing")
        sys.exit(1)
        
    with open(repo_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "JOIN cylinders c" not in content or "as vat_code" not in content:
            print("  [FAIL] wash_repo does not use cylinders join or vat_code alias")
            sys.exit(1)
        if "COALESCE" not in content and "cylinder_no" not in content:
            print("  [FAIL] wash_repo source is not cylinder_no")
            sys.exit(1)
        print("  [PASS] Data source uses cylinders join and vat_code alias correctly")

    # 2. Check Templates
    templates = [
        "src/hopaoems/templates/wash/list.html",
        "src/hopaoems/templates/wash/history.html",
        "src/hopaoems/templates/fabric/cylinder_view.html"
    ]
    
    all_ok = True
    for t in templates:
        if not os.path.exists(t):
            print(f"  [FAIL] {t} does not exist")
            all_ok = False
            continue
            
        with open(t, 'r', encoding='utf-8') as f:
            content = f.read()
            if "ui_vat_group_header" not in content:
                print(f"  [FAIL] {t} does not call ui_vat_group_header")
                all_ok = False
            elif "ui_tr" not in content:
                 print(f"  [FAIL] {t} still uses raw <tr> tags instead of ui_tr")
                 all_ok = False
            elif "wash" in t and "ui_thumbnail" not in content:
                 print(f"  [FAIL] {t} missing operator thumbnails (ui_thumbnail)")
                 all_ok = False
            else:
                print(f"  [PASS] {t} uses grouping macro, ui_tr and thumbnails")
                
    if not all_ok:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
