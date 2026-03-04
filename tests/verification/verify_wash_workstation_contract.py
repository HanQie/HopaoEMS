
import os
import sys

def verify_wash_workstation_contract():
    print("Verifying Wash Workstation Contract...")
    
    templates = ['src/templates/wash/list.html', 'src/templates/wash/history.html']
    for tp in templates:
        if not os.path.exists(tp):
            print(f"FAIL: {tp} missing")
            return False
            
    # Check for Log ID column and checkbox in list
    with open('src/templates/wash/list.html', 'r', encoding='utf-8') as f:
        list_content = f.read()
    
    if "t('production.fields.log_id')" not in list_content:
        print("FAIL: wash/list.html missing Log ID column")
        return False
        
    if "F.ui_checkbox(name='log_ids'" not in list_content:
        print("FAIL: wash/list.html missing or incorrect log_ids checkbox")
        return False

    # Check for viewer/operator permission display hint
    if "current_user.role == 'operator'" not in list_content:
        print("FAIL: wash/list.html should check for operator role for actions")
        return False

    print("PASSED")
    return True

if __name__ == "__main__":
    if not verify_wash_workstation_contract():
        sys.exit(1)
