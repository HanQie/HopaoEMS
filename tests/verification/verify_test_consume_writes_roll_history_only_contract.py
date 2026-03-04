import os
import sys

def main():
    print("GATE: TEST CONSUME ARCHITECTURAL LOCK")
    
    # 1. Route Check
    blueprint_path = "src/hopaoems/blueprints/ui_production.py"
    if not os.path.exists(blueprint_path):
        print(f"  [FAIL] {blueprint_path} missing")
        sys.exit(1)
        
    with open(blueprint_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "/task/<int:id>/test-consume" not in content:
            print("  [FAIL] missing test-consume route")
            sys.exit(1)
            
    # 2. Template Check
    template_path = "src/hopaoems/templates/production/test_consume.html"
    if not os.path.exists(template_path):
        print(f"  [FAIL] {template_path} missing")
        sys.exit(1)
        
    # 3. Repo Implementation Check (Contract)
    repo_path = "src/hopaoems/services/fabric_repo.py"
    with open(repo_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "def record_test_consume" not in content:
            print("  [FAIL] fabric_repo.record_test_consume missing")
            sys.exit(1)
            
    # 4. Strict Contract Check: Action and Isolation
    # Static scan of the function body
    import re
    func_match = re.search(r'def record_test_consume.*?(?=def|\Z)', content, re.DOTALL)
    if func_match:
        body = func_match.group(0)
        if "action" in body and "'test_consume'" not in body:
            print("  [FAIL] record_test_consume missing test_consume action contract")
            sys.exit(1)
        if "production_logs" in body:
            print("  [FAIL] record_test_consume detected writing to production_logs (VIOLATION)")
            sys.exit(1)
    
    print("  [INFO] Behavioral logic (clamp/isolation/notes) is verified by functional tests.")
    
    # 5. Domain Contract Check
    contract_path = "src/hopaoems/contracts/domain_contract.md"
    with open(contract_path, 'r', encoding='utf-8') as f:
        contract = f.read()
        if "test_consume" not in contract:
             print("  [FAIL] Domain contract not updated")
             sys.exit(1)

    print("  [PASS] Test Consume architecture verified (History-only, no production log)")
    sys.exit(0)

if __name__ == "__main__":
    main()
