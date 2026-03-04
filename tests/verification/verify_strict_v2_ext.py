import os
import re
import sys

# Policy: 0 Token in Templates (using word boundaries to avoid false positives)
# Pattern updated with \b to ensure we match class prefixes correctly
TOKEN_PATTERN = r"\bbg-|\btext-|\bborder-|\brounded-|\bshadow-|\bring-|\bpx-|\bpy-|\bmx-|\bmy-|\bgap-|\bgrid-|\bflex-|\bmax-w-|\bw-|\bh-"
ATTR_PATTERN = r"\bstyle=|\battrs="
STYLE_PROP_PATTERN = r"ALLOWED_STYLE_PROPS" # Should not be in templates

TEMPLATES_DIR = "src/hopaoems/templates"

def check_file(file_path):
    violations = []
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.splitlines()

        for i, line in enumerate(lines):
            # 1. Token Check
            if re.search(TOKEN_PATTERN, line):
                violations.append(f"L{i+1}: Forbidden Token: {line.strip()}")
            
            # 2. Attribute Check
            if re.search(ATTR_PATTERN, line):
                violations.append(f"L{i+1}: Forbidden Attribute (style/attrs): {line.strip()}")
            
            # 3. Style Prop Gate string Check
            if re.search(STYLE_PROP_PATTERN, line):
                violations.append(f"L{i+1}: Forbidden string ALLOWED_STYLE_PROPS: {line.strip()}")
    
    return violations

def main():
    print("EXTENDED STRICT STYLE GATE (v2_ext)")
    all_passed = True

    # Check all templates (excluding macros)
    for root, dirs, files in os.walk(TEMPLATES_DIR):
        if 'macros' in root: continue
        for file in files:
            if not file.endswith(".html"): continue
            
            file_path = os.path.join(root, file)
            violations = check_file(file_path)
            if violations:
                all_passed = False
                print(f"  [FAIL] {file_path}")
                for v in violations: print(f"    {v}")
            else:
                pass 

    if all_passed:
        print("\nSUMMARY: ALL TEMPLATES PASSED EXTENDED STRICT AUDIT (0 TOKEN, 0 STYLE/ATTRS).")
        sys.exit(0)
    else:
        print("\nSUMMARY: AUDIT FAILED.")
        sys.exit(1)

if __name__ == "__main__":
    main()
