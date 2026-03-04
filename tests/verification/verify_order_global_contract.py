
import sys
import os
import re

# Add src to path just in case
sys.path.append(os.path.join(os.getcwd(), 'src'))

def scan_file(filepath):
    errors = []
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')

    # 1. Zero Tailwind Tokens (Visual)
    # Block list of visual prefixes
    visual_prefixes = [
        'bg-', 'text-', 'border-', 'px-', 'py-', 'p-', 'm-', 'my-', 'mx-', 'mt-', 'mb-', 'ml-', 'mr-', 
        'rounded-', 'shadow-', 'grid-', 'flex', 'gap-', 'hover:', 'focus:', 'w-', 'h-', 'items-', 'justify-',
        'font-', 'aspect-', 'overflow-', 'group', 'ring-', 'translate-', 'scale-', 'rotate-', 'cursor-'
    ]
    
    # 2. Zero Inline JS
    inline_js = ['onclick', 'onchange', 'onsubmit', 'onmouseover', 'onmouseout', 'onkeydown', 'onkeyup', 'style=']

    # 3. Raw Tags
    raw_tags = ['<table', '<button', '<input', '<select', '<textarea', '<tr', '<td']

    # 4. Layer Rules
    # - Must use F.ui_button (or A.ui_button if actions macro)
    # - No C.ui_button (Component layer shouldn't have buttons ideally, or restricted)
    # - No F.btn (Old alias forbidden)
    
    for i, line in enumerate(lines):
        line_num = i + 1
        stripped = line.strip()
        
        # Check Tailwind matches
        for token in visual_prefixes:
            if re.search(f'[\'"]{re.escape(token)}', stripped) or re.search(f' {re.escape(token)}', stripped):
                 if token == 'text-' and 'type="text"' in stripped:
                     continue
                 errors.append(f"Line {line_num}: Visual token found: '{token}'")

        # Check Inline JS
        for js in inline_js:
             if js in stripped:
                errors.append(f"Line {line_num}: Inline JS/Style found: '{js}'")

        # Check Raw Tags
        for tag in raw_tags:
            if re.search(f'{tag}[ >]', stripped):
                errors.append(f"Line {line_num}: Raw HTML tag found: '{tag}'")

        # Layer Rule Checks
        if 'C.ui_button' in stripped:
             errors.append(f"Line {line_num}: Layer Violation: C.ui_button used. Use F.ui_button or Act.ui_button.")
        
        if 'F.btn' in stripped:
             errors.append(f"Line {line_num}: Deprecated: F.btn used. Use F.ui_button.")
             
    return errors

def verify_order_templates():
    base_dir = os.path.join(os.getcwd(), 'src', 'templates', 'order')
    files = ['list.html', 'form.html', 'view.html']
    
    all_pass = True
    
    if not os.path.exists(base_dir):
        print(f"❌ Error: Order templates directory not found: {base_dir}")
        sys.exit(1)

    print(f"Scanning {base_dir}...")

    for fname in files:
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            print(f"⚠️ Warning: File not found {fname}")
            continue
            
        errors = scan_file(fpath)
        if errors:
            print(f"❌ FAIL: {fname}")
            for e in errors:
                print(f"  - {e}")
            all_pass = False
        else:
            print(f"✅ PASS: {fname}")
            
    if all_pass:
        print("\nAll order templates passed Strict Contract.")
        sys.exit(0)
    else:
        print("\nVerification Failed.")
        sys.exit(1)

if __name__ == '__main__':
    verify_order_templates()
