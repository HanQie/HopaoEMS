import os
import sys
import re

def verify_washlist_contract():
    print("Verifying Wash List Log-Level Contract...")
    
    # 1. Check template for log_ids and log_id label
    template_path = 'src/templates/production/wash_list.html'
    if not os.path.exists(template_path):
        print(f"FAIL: {template_path} missing")
        return False
        
    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    if "name='log_ids'" not in content:
        print("FAIL: wash_list.html should use name='log_ids' for checkboxes")
        return False
        
    if "t('production.fields.log_id')" not in content:
        print("FAIL: wash_list.html should display t('production.fields.log_id')")
        return False
        
    # 2. Check ui.py for list_unwashed_logs call
    ui_path = 'src/blueprints/ui.py'
    with open(ui_path, 'r', encoding='utf-8') as f:
        ui_content = f.read()
        
    if "production_repo.list_unwashed_logs()" not in ui_content:
        print("FAIL: ui.py should call production_repo.list_unwashed_logs()")
        return False

    if "request.form.getlist('log_ids')" not in ui_content:
        print("FAIL: ui.py should extract 'log_ids' from form")
        return False

    print("PASSED")
    return True

if __name__ == "__main__":
    if not verify_washlist_contract():
        sys.exit(1)
