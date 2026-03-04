
import os
import re
import sys

# Policy Configuration
ALLOWED_HOOK_CLASSES = {
    'hidden', 'block', 'inline-block', 'flex', 'grid', # Layout Structure
    'truncate', 'whitespace-nowrap', # Text Control
    'w-full', 'h-full', # Basic Size
}
ALLOWED_ATTRS = {'id', 'name', 'type', 'value', 'placeholder', 'required', 'readonly', 'disabled', 'rows', 'cols', 'method', 'action', 'enctype', 'onclick', 'onsubmit', 'href', 'title', 'attrs', 'data-js', 'style', 'data-hook'}
# Only allow space-y-*, space-x-*, min-h-*, max-h-* via regex check if needed, 
# or strictly limit. Plan said "Clarify allowed... e.g. space-y-*".
# We'll allow space-*, min-h-*, max-h-*, gap-*? Gap usually grid/flex spacing.

ALLOWED_STYLE_PROPS = {'width', 'background-color', 'color', 'flex', 'cursor'} # Whitelist style props

def check_hook_class(value):
    """Check if hook_class content is allowed."""
    tokens = value.split()
    violations = []
    for token in tokens:
        if token in ALLOWED_HOOK_CLASSES: continue
        violations.append(token)
    return violations

def verify_templates():
    base_dir = os.path.join('src', 'hopaoems', 'templates')
    violations = []
    
    for root, dirs, files in os.walk(base_dir):
        # Skip macros directory for strict class check?
        # Macros define the tokens, so they are allowed to have raw classes.
        # But they must adhere to Morandi/Mother pattern (no loose implementation).
        # We assume macros are trusted/reviewed.
        # We strict check PAGE templates.
        
        # Check if we are in macros dir
        rel_path = os.path.relpath(root, base_dir)
        if rel_path.startswith('macros') or rel_path == 'macros':
            continue
            
        for file in files:
            if not file.endswith('.html'): continue
            if file == 'base.html': continue # Allowed base
            
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 1. Check for raw class="..." (Strict prohibition in pages)
            # Regex to find class="..." or class='...'
            # Excluding macro imports/calls
            class_matches = re.finditer(r'\bclass=[\'"]([^\'"]+)[\'"]', content)
            for m in class_matches:
                # We simply forbid ANY class attribute in page templates.
                # Exception: maybe inside <style> or <script>?
                # Simple check first.
                violations.append(f"{path}: Forbidden 'class' attribute found: '{m.group(0)}'")

            # 2. Check hook_class="..." usage
            # find hook_class='...' or hook_class="..."
            hook_matches = re.finditer(r'hook_class=[\'"]([^\'"]+)[\'"]', content)
            for m in hook_matches:
                cls_val = m.group(1)
                bad_tokens = check_hook_class(cls_val)
                if bad_tokens:
                    violations.append(f"{path}: Forbidden tokens in hook_class: {bad_tokens}")

            # 3. Check style="..."
            style_matches = re.finditer(r'\bstyle=[\'"]([^\'"]+)[\'"]', content)
            for m in style_matches:
                style_val = m.group(1)
                # Parse style props primitive way
                props = [p.split(':')[0].strip() for p in style_val.split(';') if ':' in p]
                for p in props:
                    if p not in ALLOWED_STYLE_PROPS:
                        violations.append(f"{path}: Forbidden style property '{p}' in '{m.group(0)}'")

    if violations:
        print("\n".join(violations))
        sys.exit(1)
        
    print("STRICT STYLE GATE PASSED")

if __name__ == '__main__':
    verify_templates()
