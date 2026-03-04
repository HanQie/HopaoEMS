import sys
import os
import json
import re
from jinja2 import Environment, FileSystemLoader

def setup_paths():
    contract_dir = os.path.dirname(os.path.abspath(__file__))
    root_path = os.path.abspath(os.path.join(contract_dir, '..', '..', '..'))
    src_path = os.path.join(root_path, 'src')
    return root_path, src_path

ROOT_PATH, SRC_PATH = setup_paths()
TEMPLATES_PATH = os.path.join(SRC_PATH, 'hopaoems', 'templates')
I18N_PATH = os.path.join(SRC_PATH, 'hopaoems', 'i18n')
STATIC_PATH = os.path.join(SRC_PATH, 'static')

def run_macro_gate():
    env = Environment(loader=FileSystemLoader(TEMPLATES_PATH))
    # Mock global functions to avoid execution errors during template.module access
    env.globals['t'] = lambda x, **kwargs: x
    env.globals['url_for'] = lambda x, **kwargs: x
    env.globals['get_locale'] = lambda: 'en'
    env.globals['get_flashed_messages'] = lambda **kwargs: []
    env.globals['request'] = type('MockRequest', (), {'endpoint': '', 'path': '/'})
    env.globals['is_operator'] = lambda: True
    env.globals['g'] = type('MockG', (), {'user': {'role': 'operator', 'username': 'admin'}})
    checks = [
        ('macros/ui/layout.html', 'ui_app_shell'),
        ('macros/ui/forms.html', 'ui_form'),
        ('macros/ui/forms.html', 'ui_button'),
        ('macros/ui/components.html', 'ui_card'),
        ('macros/ui/components.html', 'ui_table'),
        ('macros/ui/components.html', 'ui_badge'),
    ]
    for rel_path, macro_name in checks:
        try:
            print(f"DEBUG: Checking {macro_name} in {rel_path}...")
            template = env.get_template(rel_path)
            if not hasattr(template.module, macro_name):
                return False, f"Macro '{macro_name}' NOT FOUND in {rel_path}"
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, f"Error loading {rel_path}: {e}"
    print("PASS")
    return True, None

def run_visual_token_gate():
    print("--- 2. Zero Visual Token Gate ---")
    violations = []
    for root, dirs, files in os.walk(TEMPLATES_PATH):
        rel_root = os.path.relpath(root, TEMPLATES_PATH)
        if rel_root.startswith('macros') or rel_root == 'macros':
            continue
        for file in files:
            if not file.endswith('.html') or file == 'base.html':
                continue
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            # Match raw class="..." but ignore hook_class="..."
            # Using negative lookbehind to avoid matching hook_class
            if re.search(r'(?<!hook_)class=[\'"]', content):
                violations.append(f"Forbidden raw 'class' attribute in {os.path.relpath(path, SRC_PATH)}")
    if violations:
        return False, violations[0]
    print("PASS")
    return True, None

def run_forbidden_js_gate():
    print("--- 3. No Forbidden JS API Gate ---")
    forbidden_patterns = [
        (r'\.innerHTML\s*=', 'innerHTML assignment'),
        (r'\.insertAdjacentHTML\(', 'insertAdjacentHTML call'),
        (r'\beval\(', 'eval call'),
        (r'document\.write\(', 'document.write call'),
    ]
    scan_paths = [STATIC_PATH, TEMPLATES_PATH]
    for start_path in scan_paths:
        for root, dirs, files in os.walk(start_path):
            for file in files:
                if not (file.endswith('.js') or file.endswith('.html')):
                    continue
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                for pattern, desc in forbidden_patterns:
                    if re.search(pattern, content):
                        return False, f"Forbidden {desc} in {os.path.relpath(path, SRC_PATH)}"
    print("PASS")
    return True, None

def run_i18n_parity_gate():
    print("--- 4. i18n Key Parity Gate ---")
    langs = ['en', 'zh-TW', 'vi']
    seeds = {}
    for lang in langs:
        path = os.path.join(I18N_PATH, f'seed.{lang}.json')
        if not os.path.exists(path):
            return False, f"Missing {path}"
        with open(path, 'r', encoding='utf-8') as f:
            seeds[lang] = json.load(f)
    
    keys_en = set(seeds['en'].keys())
    for lang in ['zh-TW', 'vi']:
        keys_other = set(seeds[lang].keys())
        if keys_en != keys_other:
            diff = keys_en ^ keys_other
            return False, f"Key mismatch between en and {lang}: {list(diff)[:5]}"
    print("PASS")
    return True, None

def run_smoke_gate():
    print("--- 5. Smoke Tests Gate ---")
    try:
        from .smoke_tests import run_smoke_tests
        success, err = run_smoke_tests()
        return success, err
    except (ImportError, ValueError):
        # Fallback if run as stand-alone script without package context
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
        from hopaoems.contracts.smoke_tests import run_smoke_tests
        success, err = run_smoke_tests()
        return success, err

def run_quick_produce_minimal_inputs_gate():
    print("--- 6. Quick Produce Minimal Inputs Gate ---")
    try:
        produce_template = os.path.join(TEMPLATES_PATH, 'production', 'produce.html')
        print(f"[DEBUG] Absolute path: {os.path.abspath(produce_template)}")
        print(f"[DEBUG] File exists: {os.path.exists(produce_template)}")
        
        if not os.path.exists(produce_template):
            print("[DEBUG] File not found, skipping gate")
            return True, None
        
        print(f"[DEBUG] Reading file...")
        with open(produce_template, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"[DEBUG] File read successfully, {len(content)} bytes")
        
        # Extract name="..." from input, select, textarea
        print("[DEBUG] Extracting name attributes with regex...")
        names = re.findall(r'\bname=[\'"]([^\'"]+)[\'"]', content)
        print(f"[DEBUG] Found {len(names)} name attributes:")
        for i, name in enumerate(names):
            print(f"[DEBUG]   {i+1}. '{name}' (length: {len(name)}, repr: {repr(name)})")
        
        allowed_names = {'roll_id', 'printed_length', 'note', 'roll_depleted', 'csrf_token', 'cyl_filter', 'roll_search', 'roll_q'}
        print(f"[DEBUG] Allowed names: {sorted(allowed_names)}")
        
        forbidden = []
        for name in names:
            if name not in allowed_names:
                forbidden.append(name)
        
        if forbidden:
            print(f"[DEBUG] FAIL: Forbidden names found: {forbidden}")
            return False, f"Forbidden field name(s) {forbidden} found in production/produce.html"
        
        print("PASS")
        return True, None
    except Exception as e:
        print(f"[ERROR] Gate 6 crashed with exception:")
        import traceback
        traceback.print_exc()
        print(f"[ERROR] Exception type: {type(e).__name__}")
        print(f"[ERROR] Exception message: {str(e)}")
        return False, f"Gate 6 crashed: {str(e)}"

def run_wash_vat_header_asset_gate():
    print("--- 7. Wash Vat Header Asset Gate ---")
    targets = [
        os.path.join(TEMPLATES_PATH, 'wash', 'list.html'),
        os.path.join(TEMPLATES_PATH, 'wash', 'history.html')
    ]
    
    for path in targets:
        if not os.path.exists(path):
            continue
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 1. Must use the macro
        if 'ui_vat_group_header' not in content:
            return False, f"Missing 'ui_vat_group_header' call in {os.path.relpath(path, SRC_PATH)}"
            
        # 2. No forbidden class prefixes (already checked by Zero Visual Token, but we repeat for focus)
        forbidden = [r'bg-', r'border-', r'text-', r'style=']
        for pattern in forbidden:
            # Match outside of macros/ imports if possible, but here we just block all
            if re.search(pattern, content):
                # Special case: don't fail on t('...') results if they happen to have these, but templates shouldn't have raw ones
                return False, f"Forbidden visual token/style '{pattern}' found in {os.path.relpath(path, SRC_PATH)}"
                
    print("PASS")
    return True, None

def run_closure_contract_gate():
    print("--- 8. Done/Close Closure Contract Gate ---")
    # Verify repo has the logic
    prod_repo = os.path.join(SRC_PATH, 'hopaoems', 'services', 'production_repo.py')
    order_repo = os.path.join(SRC_PATH, 'hopaoems', 'services', 'order_repo.py')
    
    with open(prod_repo, 'r', encoding='utf-8') as f:
        if 'production.error.unwashed_logs_exist' not in f.read():
            return False, "Missing unwashed log check in production_repo"
            
    with open(order_repo, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'order.error.unwashed_logs_exist' not in content:
            return False, "Missing unwashed log check in order_repo"
        if 'order.error.unclosed_tasks_exist' not in content:
            return False, "Missing unclosed tasks check in order_repo"
            
    print("PASS")
    return True, None

def run_order_task_sync_contract_gate():
    print("--- 11. Order Task Sync Contract Gate ---")
    order_repo_path = os.path.join(SRC_PATH, 'hopaoems', 'services', 'order_repo.py')
    ui_order_path = os.path.join(SRC_PATH, 'hopaoems', 'blueprints', 'ui_order.py')
    
    # 1. Check sync_tasks_for_order exists in order_repo
    with open(order_repo_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if 'def sync_tasks_for_order' not in content:
            return False, "Missing 'sync_tasks_for_order' in order_repo.py"
            
    # 2. Check sync_tasks_for_order is used in order_repo
    if 'sync_tasks_for_order(' not in content:
        return False, "sync_tasks_for_order is not called in order_repo.py"

    # 3. Check order_edit route exists and uses update_order
    with open(ui_order_path, 'r', encoding='utf-8') as f:
        content = f.read()
        if '/edit' not in content:
            return False, "Missing order edit route in ui_order.py"
        if 'order_repo.update_order' not in content:
            return False, "order edit route does not call order_repo.update_order"

    print("PASS")
    return True, None


def run_manual_adjust_minimal_inputs_gate():
    print("--- 13. Manual Adjust Minimal Inputs Gate ---")
    template_path = os.path.join(TEMPLATES_PATH, 'fabric', 'roll_adjust_stock.html')
    
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
        # 1. Use regex to find all name="..." in the template
        import re
        names = re.findall(r'name=[\'"]([^\'"]+)[\'"]', content)
        
        allowed = {'new_length_m', 'note', 'csrf_token'}
        
        # Check if any names are not allowed
        for name in names:
             if name not in allowed:
                  return False, f"Forbidden input name '{name}' found in roll_adjust_stock.html. Allowed: {allowed}"
                  
        # 2. Check if all required names are present
        required = {'new_length_m', 'note'}
        found_names = set(names)
        for req in required:
             if req not in found_names:
                  return False, f"Missing required input name '{req}' in roll_adjust_stock.html"

    print("PASS")
    return True, None

def run_operator_only_coverage_gate():
    print("--- 14. Operator-only Coverage Gate ---")
    contract_path = os.path.join(ROOT_PATH, 'src', 'hopaoems', 'contracts', 'operator_actions_contract.json')
    print(f"Reading operator contract from: {contract_path}")
    if not os.path.exists(contract_path):
        return False, f"Missing contract file: {contract_path}"
        
    with open(contract_path, 'r', encoding='utf-8') as f:
        contract = json.load(f)
    print(f"Loaded {len(contract['operator_only_endpoints'])} operator endpoints from contract.")
    
    # We need to import the app to check routes
    import sys
    sys.path.append(SRC_PATH)
    from hopaoems.app_factory import create_app
    app = create_app({'TESTING': True, 'DATABASE': ':memory:', 'WTF_CSRF_ENABLED': False})
    
    with app.app_context():
        view_functions = app.view_functions
        for entry in contract['operator_only_endpoints']:
            endpoint = entry['endpoint']
            if endpoint not in view_functions:
                return False, f"Endpoint '{endpoint}' from contract not found in app"
            
            func = view_functions[endpoint]
            # Unwrap the function if it has multiple decorators
            if not getattr(func, '_requires_operator', False):
                return False, f"Endpoint '{endpoint}' is missing @operator_required marker"
                
    print(f"PASS ({len(contract['operator_only_endpoints'])} routes covered)")
    return True, None

def run_routes_contract_gate():
    print("--- 15. Routes Contract Gate ---")
    contract_path = os.path.join(ROOT_PATH, 'src', 'hopaoems', 'contracts', 'routes_contract.json')
    if not os.path.exists(contract_path):
        return False, f"Missing contract file: {contract_path}"
        
    with open(contract_path, 'r', encoding='utf-8') as f:
        contract = json.load(f)
        
    # Import app
    import sys
    sys.path.append(SRC_PATH)
    from hopaoems.app_factory import create_app
    app = create_app({'TESTING': True, 'DATABASE': ':memory:', 'WTF_CSRF_ENABLED': False})
    
    with app.app_context():
        # Get all registered routes from app
        registered_routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint in contract.get('ignore_endpoints', []):
                continue
            if any(rule.rule.startswith(prefix) for prefix in contract.get('ignore_rules_prefix', [])):
                continue
            registered_routes.append({
                'rule': rule.rule,
                'methods': set(rule.methods - {'HEAD', 'OPTIONS'})
            })
            
        # 1. Check Canonical Routes
        contract_canonical = contract.get('routes', [])
        for route in contract_canonical:
            rule = route['rule']
            methods = set(route['methods'])
            
            # Find in registered
            found = [r for r in registered_routes if r['rule'] == rule]
            if not found:
                return False, f"Canonical route '{rule}' from contract NOT FOUND in app"
            
            # Check methods (contract methods must be a subset of registered methods)
            found_methods = set()
            for r in found:
                found_methods.update(r['methods'])
                
            if not methods.issubset(found_methods):
                return False, f"Rule '{rule}' lacks required methods: {methods - found_methods}"

        # 2. Check Legacy Redirects
        legacy_redirects = contract.get('legacy_redirects', [])
        client = app.test_client()
        # Initialize DB and login for protected routes
        from hopaoems.services.schema_migrations import init_schema
        init_schema()
        client.post('/auth/login', data={'username': 'admin', 'password': 'admin'})
        
        for red in legacy_redirects:
            rule_from = red['from']
            rule_to = red['to']
            methods = red['methods']
            
            # Verify route exists in app
            found = [r for r in registered_routes if r['rule'] == rule_from]
            if not found:
                return False, f"Legacy route '{rule_from}' NOT FOUND in app"
            
            # Verify it redirects to target (302)
            # Use dummy IDs if needed for the test request
            test_url = rule_from.replace('<int:id>', '1').replace('<id>', '1')
            for method in methods:
                res = client.open(test_url, method=method)
                if res.status_code != 302:
                    return False, f"Legacy route '{rule_from}' failed to redirect (Got {res.status_code})"
                if res.location.replace('http://localhost', '') != rule_to:
                    return False, f"Legacy route '{rule_from}' redirects to wrong location: {res.location}"

        # 3. Prevent Drift (No unmanaged routes)
        canonical_rules = {r['rule'] for r in contract_canonical}
        legacy_from_rules = {r['from'] for r in legacy_redirects}
        for reg in registered_routes:
            if reg['rule'] not in canonical_rules and reg['rule'] not in legacy_from_rules:
                return False, f"Drift Detected: Route '{reg['rule']}' is registered in app but NOT in routes_contract.json"

    print(f"PASS ({len(contract_canonical)} canonical routes, {len(legacy_redirects)} legacy redirects)")
    return True, None

def run_sample_path_contract_gate():
    print("--- 16. Sample Path Contract Gate ---")
    import re
    # Patterns that indicate hardcoded image paths for samples
    forbidden_patterns = [
        r'uploads/samples',
        r'/data/uploads/samples'
    ]
    
    violations = []
    for root, dirs, files in os.walk(TEMPLATES_PATH):
        if 'macros' in root:
            continue
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    for p in forbidden_patterns:
                        if re.search(p, content):
                            violations.append(f"{os.path.relpath(path, TEMPLATES_PATH)} contains '{p}'")
                    # Check for manual <img> src with samples
                    if re.search(r'<img[^>]+src=[^>]*samples', content):
                        violations.append(f"{os.path.relpath(path, TEMPLATES_PATH)} contains manual <img> with samples path")

    if violations:
        return False, f"Hardcoded sample paths detected: {violations}"
    
    print("PASS")
    return True, None

def run_db_schema_contract_gate():
    print("--- 17. DB Schema Contract Gate ---")
    contract_path = os.path.join(ROOT_PATH, 'src', 'hopaoems', 'contracts', 'db_schema_contract.json')
    print(f"Reading DB schema contract from: {os.path.abspath(contract_path)}")
    if not os.path.exists(contract_path):
        return False, f"Missing contract file: {contract_path}"
        
    with open(contract_path, 'r', encoding='utf-8') as f:
        contract = json.load(f)
        
    # Generate current schema from fresh DB
    # We can reuse export logic but as a function here
    import sys
    sys.path.append(os.path.join(ROOT_PATH, 'src', 'hopaoems', 'contracts'))
    from export_db_schema_contract import get_db_schema
    
    current_schema = get_db_schema()
    
    # Compare
    errors = []
    
    contract_tables = contract.get('tables', {})
    current_tables = current_schema.get('tables', {})
    
    # 1. Check for missing or extra tables
    for table_name in contract_tables:
        if table_name not in current_tables:
            errors.append(f"Missing Table: {table_name}")
            
    for table_name in current_tables:
        if table_name not in contract_tables:
            errors.append(f"Extra Table Detected: {table_name} (Not in contract)")
            
    # 2. Check each table details
    for table_name in contract_tables:
        if table_name not in current_tables:
            continue
            
        c_table = contract_tables[table_name]
        cur_table = current_tables[table_name]
        
        # Columns
        c_cols = {c['name']: c for c in c_table['columns']}
        cur_cols = {c['name']: c for c in cur_table['columns']}
        
        for cname in c_cols:
            if cname not in cur_cols:
                errors.append(f"Table {table_name}: Missing Column {cname}")
            else:
                # Compare attributes
                for attr in ['type', 'notnull', 'pk', 'default']:
                    if c_cols[cname][attr] != cur_cols[cname][attr]:
                         errors.append(f"Table {table_name}, Col {cname}: {attr} mismatch ('{c_cols[cname][attr]}' vs '{cur_cols[cname][attr]}')")
                         
        for cname in cur_cols:
            if cname not in c_cols:
                errors.append(f"Table {table_name}: Extra Column detected {cname}")
                
        # Indexes (by name)
        c_idxs = {i['name']: i for i in c_table.get('indexes', [])}
        cur_idxs = {i['name']: i for i in cur_table.get('indexes', [])}
        
        for iname in c_idxs:
            if iname not in cur_idxs:
                # Note: sqlite_autoindex names can change, but for deterministic init_schema they should be same.
                errors.append(f"Table {table_name}: Missing Index {iname}")
            else:
                if c_idxs[iname]['unique'] != cur_idxs[iname]['unique'] or c_idxs[iname]['columns'] != cur_idxs[iname]['columns']:
                    errors.append(f"Table {table_name}: Index {iname} mismatch")
                    
        for iname in cur_idxs:
            if iname not in c_idxs:
                errors.append(f"Table {table_name}: Extra Index detected {iname}")

    if errors:
        return False, "\n".join(errors)
        
    print(f"PASS ({len(contract_tables)} tables verified)")
    return True, None

def run_i18n_key_coverage_gate():
    print("--- 18. i18n Key Coverage Gate ---")
    import re
    
    # 1. Load all seed keys
    langs = ['en', 'zh-TW', 'vi']
    seed_keys = {lang: set() for lang in langs}
    for lang in langs:
        seed_path = os.path.join(ROOT_PATH, 'src', 'hopaoems', 'i18n', f'seed.{lang}.json')
        if os.path.exists(seed_path):
            with open(seed_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                seed_keys[lang] = set(data.keys())
    
    # 2. Extract keys from templates
    template_dir = os.path.join(ROOT_PATH, 'src', 'hopaoems', 'templates')
    macro_dir = os.path.join(template_dir, 'macros')
    found_keys = set()
    
    # Regex for t('...') or t("...")
    # Matches t('key') or t("key") or t('key', ...)
    t_regex = re.compile(r"t\(\s*['\"]([^'\"]+)['\"]")
    
    for root, _, files in os.walk(template_dir):
        if root.startswith(macro_dir):
            continue
        for file in files:
            if file.endswith('.html'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    matches = t_regex.findall(content)
                    for m in matches:
                        found_keys.add(m)
    
    # 3. Verify
    missing_map = {lang: [] for lang in langs}
    for key in sorted(found_keys):
        for lang in langs:
            if key not in seed_keys[lang]:
                missing_map[lang].append(key)
    
    total_missing = sum(len(v) for v in missing_map.values())
    if total_missing > 0:
        print("FAIL: Missing i18n keys detected!")
        for lang in langs:
            if missing_map[lang]:
                print(f"\nMissing in '{lang}':")
                for key in sorted(missing_map[lang]):
                    print(f"  - {key}")
        return False, f"Total missing keys: {total_missing}"
        
    print(f"PASS ({len(found_keys)} unique keys verified across all templates)")
    return True, None

def main():
    gates = [
        run_macro_gate,
        run_visual_token_gate,
        run_forbidden_js_gate,
        run_i18n_parity_gate,
        run_i18n_key_coverage_gate,
        run_quick_produce_minimal_inputs_gate,
        run_wash_vat_header_asset_gate,
        run_closure_contract_gate,
        run_order_task_sync_contract_gate,
        run_manual_adjust_minimal_inputs_gate,
        run_operator_only_coverage_gate,
        run_routes_contract_gate,
        run_sample_path_contract_gate,
        run_db_schema_contract_gate,
        run_smoke_gate
    ]
    for gate in gates:
        success, err = gate()
        if not success:
            print(f"\nGATE STATUS: FAIL")
            print(f"ERROR: {err}")
            sys.exit(1)
    print("\nGATE STATUS: PASS (All layers verified)")

if __name__ == "__main__":
    main()
