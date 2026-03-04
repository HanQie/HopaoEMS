from jinja2 import Environment, FileSystemLoader
import os

root = r'c:\Users\JingHu\Desktop\hopaoems2\src\hopaoems\templates'
env = Environment(loader=FileSystemLoader(root))
env.globals['t'] = lambda x, **k: x
env.globals['url_for'] = lambda x, **k: x
class MockRequest:
    args = {}
    endpoint = 'test'
env.globals['request'] = MockRequest()
env.globals['is_operator'] = lambda: True

try:
    tmpl = env.get_template('macros/ui/components.html')
    print("Macros found:", [m for m in dir(tmpl.module) if not m.startswith('_')])
    
    if hasattr(tmpl.module, 'ui_fmt_length_m'):
        print("ui_fmt_length_m is PRESENT")
    else:
        print("ui_fmt_length_m is MISSING")

except Exception as e:
    print("Error loading template:", e)
    import traceback
    traceback.print_exc()
