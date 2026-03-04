import re
import os

TEMPLATES_PATH = r'c:\Users\JingHu\Desktop\hopaoems2\src\hopaoems\templates'
produce_template = os.path.join(TEMPLATES_PATH, 'production', 'produce.html')

if not os.path.exists(produce_template):
    print("Template not found")
else:
    try:
        with open(produce_template, 'r', encoding='utf-8') as f:
            content = f.read()
        
        names = re.findall(r'\bname=[\'"]([^\'"]+)[\'"]', content)
        print("Found names:", names)
        
        allowed_names = {'roll_id', 'printed_length', 'note', 'roll_depleted', 'csrf_token', 'cyl_filter', 'roll_search', 'roll_q'}
        for name in names:
            if name not in allowed_names:
                print(f"Forbidden: {name}")
        print("Done")
    except Exception as e:
        print(f"Error: {e}")
