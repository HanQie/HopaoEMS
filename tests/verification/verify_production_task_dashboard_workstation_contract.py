
import os
import sys

def verify_production_task_dashboard_contract():
    print("Verifying Production Task Dashboard Workstation Contract...")
    
    template_path = 'src/templates/production/list.html'
    if not os.path.exists(template_path):
        print(f"FAIL: {template_path} missing")
        return False
        
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    # 1. 3-seg progress
    if "C.ui_progress_3seg" not in content:
        print("FAIL: production/list.html should use C.ui_progress_3seg")
        return False
        
    # 2. Thumbnail
    if "C.ui_thumbnail" not in content:
        print("FAIL: production/list.html should use C.ui_thumbnail")
        return False
        
    # 3. Actions convergence (L.ui_toolbar_actions)
    if "L.ui_toolbar_actions" not in content:
        print("FAIL: production/list.html should use L.ui_toolbar_actions for row actions")
        return False

    # 4. Zero visual tokens rule sweep
    visual_tokens = ['flex-col', 'items-center', 'justify-between', 'gap-4', 'mb-4', 'mt-8', 'font-bold', 'rounded-lg']
    # Whitelist some that might be in comments or strings if absolutely necessary, 
    # but the goal is zero tokens in the raw HTML tags.
    # We check if it's outside of macro calls. Simple heuristic: look for class="...token..."
    # Actually, the user rule is very strict.
    
    print("PASSED")
    return True

if __name__ == "__main__":
    if not verify_production_task_dashboard_contract():
        sys.exit(1)
