
import sys
import os
import subprocess
import time

# Define the ordered list of gates to run
CORE_GATES = [
    ("Gate 1: Topbar Identity", ".agent/skills/hopaoems-system/scripts/verify_topbar_identity.py"),
    ("Gate 2: Nav Active Contract", ".agent/skills/hopaoems-system/scripts/verify_nav_active_contract.py"),
    ("Gate 3: Stat Card Contract", ".agent/skills/hopaoems-system/scripts/verify_stat_card_contract.py"),
    ("Gate 4: Table Density Contract", ".agent/skills/hopaoems-system/scripts/verify_table_density_contract.py"),
    ("Gate 5: List Toolbar Contract", ".agent/skills/hopaoems-system/scripts/verify_list_toolbar_contract.py"),
    ("Gate 6: User Menu Contract", ".agent/skills/hopaoems-system/scripts/verify_user_menu_contract.py"),
    ("Gate 7: Base HTML Zero Token", ".agent/skills/hopaoems-system/scripts/verify_base_zero_token.py"), # We will create a script wrapper for this or inline logic
    # Gate 7 was inline logic re: base.html. To make it consistent, we should ideally script it,
    # but for now we can wrap it or handle it as special case. 
    # Actually, to be robust, let's create a temporary script for it or keep it inline but simulated as a runner step.
    # The request says "Modify verify_gates_snapshot.py", so we can refactor logic.
    
    ("Gate 8: Breadcrumb Contract", ".agent/skills/hopaoems-system/scripts/verify_breadcrumb_contract.py"),
    ("Gate 9: Sidebar Collapse Contract", ".agent/skills/hopaoems-system/scripts/verify_sidebar_collapse_contract.py"),
    ("Gate 10: Sidebar Persistence Contract", ".agent/skills/hopaoems-system/scripts/verify_sidebar_persistence_contract.py"),
    ("Gate 11: Crumbs Coverage Contract", ".agent/skills/hopaoems-system/scripts/verify_crumbs_coverage_contract.py"),
    ("Gate 12: Dashboard OS Contract", ".agent/skills/hopaoems-system/scripts/verify_dashboard_os_contract.py"),
    ("Gate 13: Table Actions Contract", ".agent/skills/hopaoems-system/scripts/verify_table_actions_contract.py"),
    ("Gate 14: Table Columns Order Contract", ".agent/skills/hopaoems-system/scripts/verify_table_columns_order_contract.py"),
    ("Gate 15: Empty State Contract", ".agent/skills/hopaoems-system/scripts/verify_empty_state_contract.py"),
    ("Gate 16: Delete Flow Contract", ".agent/skills/hopaoems-system/scripts/verify_delete_flow_contract.py"),
    ("Gate 17: Testing Auth Hook Contract", ".agent/skills/hopaoems-system/scripts/verify_testing_auth_hook_contract.py"),
    ("Gate 18: Production Status Contract", ".agent/skills/hopaoems-system/scripts/verify_production_status_contract.py"),
    ("Gate 19: Status Badge Allowlist Contract", ".agent/skills/hopaoems-system/scripts/verify_status_badge_allowlist_contract.py"),
    ("Gate 20: Sidebar Single-Visible Contract", ".agent/skills/hopaoems-system/scripts/verify_sidebar_single_visible_contract.py"),
    ("Gate 21: UI Button Hook Class Contract", ".agent/skills/hopaoems-system/scripts/verify_ui_button_hook_class_contract.py"),
    ("Gate 22: Fabric Hierarchy Contract", ".agent/skills/hopaoems-system/scripts/verify_fabric_hierarchy_contract.py"),
    ("Gate 23: UI Input Attribute Contract", ".agent/skills/hopaoems-system/scripts/verify_ui_input_attr_contract.py"),
    ("Gate 24: Sample Module Contract", ".agent/skills/hopaoems-system/scripts/verify_sample_module_contract.py"),
    ("Gate 25: Sample TIFF Preview Contract", ".agent/skills/hopaoems-system/scripts/verify_sample_tiff_preview_contract.py"),
    ("Gate 26: Lightbox Contract", ".agent/skills/hopaoems-system/scripts/verify_lightbox_contract.py"),
    ("Gate 27: i18n Sample Keys Present", ".agent/skills/hopaoems-system/scripts/verify_i18n_sample_keys_present.py"),
    ("Gate 28: Sample List Grid Contract", ".agent/skills/hopaoems-system/scripts/verify_sample_list_grid_contract.py"),
    ("Gate 29: Quick Produce Contract", "verify_quick_produce_minimal_form_contract.py"),
    ("Gate 30: Order Creates Tasks Contract", "verify_order_creates_tasks_contract.py"),
    ("Gate 31: Edit Order Preserves Tasks", "verify_order_edit_task_sync_preserves_logged_tasks_contract.py"),
    ("Gate 32: Order Close Requirements", "verify_order_close_requires_all_tasks_done_and_zero_unwashed_logs_contract.py"),
    ("Gate 33: Task Done Requirements", "verify_task_done_requires_zero_unwashed_logs_contract.py"),
    ("Gate 34: Buttons Operator Only", "verify_done_close_buttons_operator_only_contract.py"),
    ("Gate 35: Summary Cards Contract", "verify_order_task_summary_cards_contract.py"),
    ("Gate 36: Vat Strip Macro", "verify_vat_strip_macro_contract.py"),
    ("Gate 37: Vat Grouping Applied", "verify_vat_grouping_applied_contract.py"),
    ("Gate 38: Vat Color Deterministic", "verify_vat_color_deterministic_contract.py"),
    ("Gate 39: Vat Data Source Lock", "verify_vat_data_source.py"),
    ("Gate 40: Vat Grouping Behavior Lock", "verify_vat_grouping_behavior.py"),
    ("Gate 41: Test Consume Architecture", "verify_test_consume_writes_roll_history_only_contract.py"),
    ("Gate 42: Task View Logs Table", "verify_task_view_has_logs_table_contract.py"),
]

LOG_DIR = os.path.join(".agent", "logs")

def ensure_log_dir():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)

def run_gate(name, script_path):
    # Ensure script path is absolute or correct relative
    if not os.path.exists(script_path):
        # Fallback to try relative to cwd if needed, but list above has relative paths
        pass

    log_file = os.path.join(LOG_DIR, f"{name.split(':')[0].lower().replace(' ', '_')}.log")
    
    start_time = time.time()
    
    try:
        # Special handling for strict python execution
        cmd = [sys.executable, script_path]
        
        # Capture strictly
        result = subprocess.run(
            cmd, 
            cwd=os.getcwd(),
            capture_output=True, 
            text=True
        )
        
        duration = time.time() - start_time
        
        # Write logs
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"=== {name} Execution Log ===\n")
            f.write(f"Time: {time.ctime()}\n")
            f.write(f"Exit Code: {result.returncode}\n")
            f.write("--- STDOUT ---\n")
            f.write(result.stdout)
            f.write("\n--- STDERR ---\n")
            f.write(result.stderr)
            
        return result.returncode == 0, log_file, duration

    except Exception as e:
        with open(log_file, "w", encoding="utf-8") as f:
            f.write(f"=== {name} CRTICAL ERROR ===\n")
            f.write(str(e))
        return False, log_file, time.time() - start_time

def check_base_html_zero_token():
    # Helper to replace inline check for Gate 7
    # We'll just run this function and return (success, log_info)
    import re
    base_path = os.path.join('src', 'templates', 'base.html')
    log_file = os.path.join(LOG_DIR, "gate_7_base_token.log")
    
    with open(log_file, "w", encoding="utf-8") as f:
        f.write("=== Gate 7: Base HTML Zero Token Log ===\n")
        if not os.path.exists(base_path):
            f.write("base.html not found!\n")
            return False, log_file, 0
            
        with open(base_path, 'r', encoding='utf-8') as bf:
            content = bf.read()
            # Banning class= but allowing macro imports? 
            # The original logic: found = re.search(r'class=["\'].*?["\']', content)
            # This is very strict, it bans `class="anything"`.
            # Let's preserve that logic.
            found = re.search(r'class=["\'].*?["\']', content)
            if found:
                 f.write(f"FAILED: Found class attribute: {found.group(0)}\n")
                 return False, log_file, 0
            else:
                 f.write("PASSED: No class attributes found.\n")
                 return True, log_file, 0

def main():
    print(f"Starting Snapshot Verification Runner...")
    ensure_log_dir()
    
    all_passed = True
    failed_bridges = []
    
    # 1. Run Script Gates
    for name, script in CORE_GATES:
        # Special dispatch for Gate 7 if it's the inline one?
        # Actually in the list above I put a script path for Gate 7.
        # But that script doesn't exist yet unless we create it.
        # To strictly follow "Modify verify_gates_snapshot.py", 
        # I should probably just inline logical check for Gate 7 inside the loop or create the script.
        # Let's create the script for Gate 7 dynamically or use the inline helper if the path matches a distinct marker.
        
        if "verify_base_zero_token.py" in script:
             success, log, dur = check_base_html_zero_token()
        else:
             success, log, dur = run_gate(name, script)
        
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} | {name} ({dur:.2f}s)")
        
        if not success:
            all_passed = False
            failed_bridges.append((name, log))

    print("-" * 40)
    if all_passed:
        print("🎉 ALL GATES PASSED. Snapshot is stable.")
        sys.exit(0)
    else:
        print("💥 SOME GATES FAILED.")
        print("Failure Details:")
        for name, log in failed_bridges:
            print(f"  - {name}")
            print(f"    Log: {log}")
        sys.exit(1)

if __name__ == "__main__":
    main()
