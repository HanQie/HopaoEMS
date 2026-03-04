import os
import sys

def main():
    print("GATE: VAT DATA SOURCE LOCK")
    repo_path = "src/hopaoems/services/wash_repo.py"
    
    if not os.path.exists(repo_path):
        print(f"  [FAIL] {repo_path} missing")
        sys.exit(1)
        
    with open(repo_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # Positive assertions
        if "JOIN cylinders c" not in content:
            print("  [FAIL] Missing 'JOIN cylinders c'")
            sys.exit(1)
        if "COALESCE(c.cylinder_no, '(UNKNOWN)') as vat_code" not in content:
            print("  [FAIL] Missing 'COALESCE(c.cylinder_no, \"(UNKNOWN)\") as vat_code'")
            sys.exit(1)
            
        # Negative assertions (Blacklist)
        if "f.fabric_code as vat_code" in content:
            print("  [FAIL] Forbidden source 'f.fabric_code as vat_code' detected")
            sys.exit(1)
            
    print("  [PASS] Repo enforces cylinder-based vat_code with fallback")
    sys.exit(0)

if __name__ == "__main__":
    main()
