import os
from jinja2 import Environment, FileSystemLoader

env = Environment(loader=FileSystemLoader('src/hopaoems/templates'))
for root, _, files in os.walk('src/hopaoems/templates'):
    for f in files:
        if f.endswith('.html'):
            rel = os.path.relpath(os.path.join(root, f), 'src/hopaoems/templates').replace('\\', '/')
            try:
                env.get_template(rel)
            except Exception as e:
                print(f"ERROR IN {rel}: {e}")
