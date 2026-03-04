import sys
import os
from jinja2 import Environment, FileSystemLoader

def verify_macros():
    # Base path for templates
    # This script is in src/hopaoems/contracts/
    contract_dir = os.path.dirname(os.path.abspath(__file__))
    templates_path = os.path.abspath(os.path.join(contract_dir, '..', 'templates'))
    
    if not os.path.exists(templates_path):
        print(f"CRITICAL: Templates directory not found at {templates_path}")
        sys.exit(1)

    env = Environment(loader=FileSystemLoader(templates_path))
    
    # Required macros per contract
    checks = [
        ('macros/ui/layout.html', 'ui_app_shell'),
        ('macros/ui/forms.html', 'ui_form'),
        ('macros/ui/forms.html', 'ui_button'),
        ('macros/ui/components.html', 'ui_card'),
        ('macros/ui/components.html', 'ui_table'),
    ]
    
    failed = False
    print(f"--- Macro Existence Gate ---")
    print(f"Templates Path: {templates_path}\n")

    for rel_path, macro_name in checks:
        full_path = os.path.join(templates_path, rel_path)
        if not os.path.exists(full_path):
            print(f"FAILED: Template file missing: {rel_path}")
            failed = True
            continue

        try:
            # We use get_template().module to inspect exported macros
            template = env.get_template(rel_path)
            # Accessing the module property triggers macro discovery
            mod = template.module
            if not hasattr(mod, macro_name):
                print(f"FAILED: Macro '{macro_name}' NOT FOUND in {rel_path}")
                failed = True
            else:
                print(f"PASSED: Macro '{macro_name}' found in {rel_path}")
        except Exception as e:
            print(f"ERROR evaluating {rel_path}: {e}")
            failed = True
            
    if failed:
        print("\nGate Status: FAIL")
        sys.exit(1)
    
    print("\nGate Status: PASS")

if __name__ == "__main__":
    verify_macros()
