
import os
import re

def scan_templates(dirs):
    # Regex to find class= or style= NOT followed by hook_class or inside macros/
    # Actually, simpler: find ALL class= and style= and filter out known OK ones.
    violations = []
    class_pattern = re.compile(r'(?:\sclass=[\"\']([^\"\']+)[\"\'])|(?:\sstyle=[\"\']([^\"\']+)[\"\'])')
    
    for d in dirs:
        for root, _, files in os.walk(d):
            for f in files:
                if not f.endswith('.html'): continue
                path = os.path.join(root, f)
                with open(path, 'r', encoding='utf-8') as file:
                    content = file.read()
                    matches = class_pattern.finditer(content)
                    for m in matches:
                        # Full match text
                        full_match = m.group(0)
                        # Filter out hook_class
                        if 'hook_class=' in full_match: continue
                        # Filter out style= if it's in a snippet we know is OK (none in production/wash)
                        # But we are strict: 0 matches for raw class/style.
                        
                        # Extra check: if it's class="{{ ... }}" it might be okay? 
                        # User says "0 matches for class=|style=".
                        violations.append(f"{path}: {full_match.strip()}")
                        
    return violations

if __name__ == "__main__":
    base = r'c:\Users\JingHu\Desktop\hopaoems2\src\hopaoems\templates'
    dirs = [
        os.path.join(base, 'production'),
        os.path.join(base, 'wash'),
        os.path.join(base, 'sample'),
        os.path.join(base, 'order'),
        os.path.join(base, 'ink'),
        os.path.join(base, 'fabric'),
    ]
    # Scan only list/view/form/produce html files, or all files in these dirs
    violations = scan_templates(dirs)
    if not violations:
        print("SCAN RESULT: 0 violations found. (PASS)")
    else:
        print(f"SCAN RESULT: {len(violations)} violations found:")
        for v in violations:
            print(v)
