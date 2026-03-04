import os
import sys
import re

def verify_order_fields_and_cascade_contract():
    print("Verifying Order Fields and Cascade Contract (Stricter)...")
    errors = []
    
    # Target files to scan
    order_templates = ['list.html', 'form.html', 'view.html']
    template_dir = os.path.join('src', 'templates', 'order')

    for filename in order_templates:
        path = os.path.join(template_dir, filename)
        if not os.path.exists(path):
            errors.append(f"Missing template: {path}")
            continue
            
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 1. Style Check (Policy: 0 hits for style=)
            if 'style=' in content:
                errors.append(f"Forbidden inline style=' found in {filename}")
                
            # 2. Raw Tag Check (Policy: 0 hits for raw input/select/table/button outside of macros)
            # We use regex to find tags not inside Jinja comments or template tags
            # Actually, the user says "Raw form/table elements (必須 0 hits) <table|<button|<input|<select|<textarea"
            if re.search(r'<(table|button|input|select|textarea)\b', content):
                # Exception: <template> is allowed but its content should still be macro-based if possible.
                # However, the user specifically mentioned <table|<button|<input|<select|<textarea.
                # If these appear, it's an error.
                errors.append(f"Raw HTML tag found in {filename}: {re.search(r'<(table|button|input|select|textarea)', content).group()}")

            # 3. Token Check
            if re.search(r'\b(bg-|text-|border-|px-|py-|p-|m-|rounded-|shadow-|grid-|flex-|gap-|hover:|focus:)', content):
                 errors.append(f"Visual token found in {filename}")

            # 4. Specific Hooks and Compliance for form.html
            if filename == 'form.html':
                if 'data-hook="order-sample-map"' not in content:
                    errors.append("Missing data-hook='order-sample-map' in form.html")
                if 'A.ui_data_payload' not in content:
                    errors.append("Missing A.ui_data_payload call in form.html")
                if 'type="application/json"' in content:
                    errors.append("Forbidden <script type='application/json'> found in form.html")
                
                # Check for customer_name removal
                if 'customer_name' in content and 'name="customer_name"' in content:
                    errors.append("customer_name field should be removed from form.html")
                
                # Check for qty[] rename
                if 'qty[]' not in content:
                    errors.append("qty[] naming should be used (not quantity[]) in form.html")
                if 'quantity[]' in content:
                    errors.append("quantity[] naming found in form.html, should be qty[]")

                # JS API Check in form.html <script>
                scripts = re.findall(r'<script.*?> (.*?) </script>', content, re.DOTALL)
                for script in scripts:
                    if re.search(r'(\.innerHTML|\.outerHTML|\.classList\.|.style\.)', script):
                        errors.append(f"Forbidden JS API found in script block in form.html")

    # 5. Global JS API Check (excluding legacy ui.js if needed, but let's be strict for now as requested)
    js_dir = os.path.join('src', 'static', 'js')
    if os.path.exists(js_dir):
        for file in os.listdir(js_dir):
            if file.endswith('.js'):
                if file == 'ui.js': continue # Skip legacy ui.js
                with open(os.path.join(js_dir, file), 'r', encoding='utf-8') as f:
                    js_content = f.read()
                    if re.search(r'(\.innerHTML|\.outerHTML|\.classList\.|.style\.)', js_content):
                        errors.append(f"Forbidden JS API found in {file}")

    if errors:
        print("FAILED")
        for e in errors:
            print(f"- {e}")
        sys.exit(1)
    else:
        print("PASSED")
        sys.exit(0)

if __name__ == "__main__":
    verify_order_fields_and_cascade_contract()
