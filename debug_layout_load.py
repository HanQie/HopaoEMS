from jinja2 import Environment, FileSystemLoader
import os
import traceback

root = r'c:\Users\JingHu\Desktop\hopaoems2\src\hopaoems\templates'
env = Environment(loader=FileSystemLoader(root))
# Mock globals needed for layout
env.globals['t'] = lambda x, **k: x
env.globals['url_for'] = lambda x, **k: x
env.globals['get_locale'] = lambda: 'en'
env.globals['get_flashed_messages'] = lambda **k: []
class MockRequest:
    endpoint = 'test'
    path = '/'
env.globals['request'] = MockRequest()
env.globals['is_operator'] = lambda: True

try:
    print("Loading macros/ui/layout.html...")
    tmpl = env.get_template('macros/ui/layout.html')
    print("Loaded. Module attributes:")
    print(dir(tmpl.module))
    
    if hasattr(tmpl.module, 'ui_app_shell'):
        print("ui_app_shell FOUND")
    else:
        print("ui_app_shell MISSING")

except Exception:
    traceback.print_exc()
