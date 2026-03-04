import re
import os
import sys

TEMPLATES_PATH = r'c:\Users\JingHu\Desktop\hopaoems2\src\hopaoems\templates'

def run_quick_produce_minimal_inputs_gate():
    print("--- 6. Quick Produce Minimal Inputs Gate ---")
    produce_template = os.path.join(TEMPLATES_PATH, 'production', 'produce.html')
    if not os.path.exists(produce_template):
        return True, None # Skip if not found
    
    try:
        with open(produce_template, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract name="..." from input, select, textarea
        # We look for name='...' or name="..."
        names = re.findall(r'\bname=[\'"]([^\'"]+)[\'"]', content)
        
        allowed_names = {'roll_id', 'printed_length', 'note', 'roll_depleted', 'csrf_token', 'cyl_filter', 'roll_search', 'roll_q'}
        for name in names:
            if name not in allowed_names:
                return False, f"Forbidden field name '{name}' found in production/produce.html"
        print("PASS")
        return True, None
    except Exception as e:
        print(f"ERROR in gate: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

success, err = run_quick_produce_minimal_inputs_gate()
if not success:
    print(f"FAIL: {err}")
    sys.exit(1)
print("All done!")
