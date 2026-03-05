import re
import os

produce_template = r"C:\Users\JingHu\Desktop\hopaoems2c\src\hopaoems\templates\production\produce.html"
with open(produce_template, 'r', encoding='utf-8') as f:
    content = f.read()

names = re.findall(r'\bname=[\'"]([^\'"]+)[\'"]', content)
allowed_names = {'roll_id', 'printed_length', 'note', 'roll_depleted', 'csrf_token', 'cyl_filter', 'roll_search', 'roll_q'}

forbidden = []
for name in names:
    if name not in allowed_names:
        forbidden.append(name)

print(f"Found names: {names}")
print(f"Forbidden names: {forbidden}")
if forbidden:
    print("GATE FAIL")
else:
    print("GATE PASS")
