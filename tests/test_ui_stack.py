
from jinja2 import Environment, FileSystemLoader
import os

env = Environment(loader=FileSystemLoader('.'))

def test_t(key): return key
env.globals['t'] = test_t

template_str = """
{% import 'src/templates/macros/ui/layout.html' as L %}
{% call L.ui_stack(gap='99') %}test{% endcall %}
"""

template = env.from_string(template_str)
print(template.render())
