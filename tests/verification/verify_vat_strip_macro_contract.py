import os
import sys
import re

def verify_macro_exists():
    path = "src/hopaoems/templates/macros/ui/components.html"
    if not os.path.exists(path):
        return False, "components macro file missing"
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
        if "{% macro ui_vat_group_header" not in content:
            return False, "ui_vat_group_header macro not found"
    return True, "Passed"

def verify_templates_clean():
    # Templates should use the macro but not raw tokens
    # Re-use logic from verify_strict_v2_ext.py
    TOKEN_PATTERN = r"\bbg-|\btext-|\bborder-|\brounded-|\bshadow-|\bring-|\bpx-|\bpy-|\bmx-|\bmy-|\bgap-|\bgrid-|\bflex-|\bmax-w-|\bw-|\bh-"
    ATTR_PATTERN = r"\bstyle=|\battrs="
    TAG_PATTERN = r"<tr\b|<td\b|<table\b" # Enforce macro usage
    
    templates = [
        "src/hopaoems/templates/wash/list.html",
        "src/hopaoems/templates/wash/history.html",
        "src/hopaoems/templates/fabric/cylinder_view.html"
    ]
    
    violations = []
    for t in templates:
        if not os.path.exists(t): continue
        with open(t, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if re.search(TOKEN_PATTERN, line):
                    violations.append(f"{t} L{i+1}: Token found")
                if re.search(ATTR_PATTERN, line):
                    violations.append(f"{t} L{i+1}: style/attrs found")
                if re.search(TAG_PATTERN, line):
                    violations.append(f"{t} L{i+1}: raw tag found ({re.search(TAG_PATTERN, line).group(0)})")
    
    if violations:
        return False, "\n".join(violations)
    return True, "Passed"

def main():
    print("GATE: VAT STRIP MACRO CONTRACT")
    m_ok, m_msg = verify_macro_exists()
    if not m_ok:
        print(f"  [FAIL] {m_msg}")
        sys.exit(1)
    
    t_ok, t_msg = verify_templates_clean()
    if not t_ok:
        print(f"  [FAIL] {t_msg}")
        sys.exit(1)
        
    print("  [PASS] Macro exists and templates are clean.")
    sys.exit(0)

if __name__ == "__main__":
    main()
