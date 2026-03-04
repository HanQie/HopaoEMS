import os
import sys

def main():
    print("GATE: TASK VIEW LOGS & ACTIONS LOCK")
    template_path = "src/hopaoems/templates/production/view.html"
    
    if not os.path.exists(template_path):
        print(f"  [FAIL] {template_path} missing")
        sys.exit(1)
        
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Check logs table existence
        if "production.logs.title" not in content:
            print("  [FAIL] missing logs table title")
            sys.exit(1)
            
        # Check thumbnail macro call
        if "ui_thumbnail" not in content:
            print("  [FAIL] missing thumbnails in logs table")
            sys.exit(1)
            
        # Check test-consume button
        if "production.action.test_consume" not in content:
            print("  [FAIL] missing test-consume action button")
            sys.exit(1)
            
        # Check ui_tr usage (Zero Raw Tag)
        if "<tr>" in content:
            print("  [FAIL] found raw <tr> tags (VIOLATION)")
            sys.exit(1)
            
    print("  [PASS] Task view contains logs table and test-consume actions")
    sys.exit(0)

if __name__ == "__main__":
    main()
