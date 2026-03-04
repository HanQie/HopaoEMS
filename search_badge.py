import os
import re

def search():
    root = r'c:\Users\JingHu\Desktop\hopaoems2\src\hopaoems\templates\macros\ui'
    for file in os.listdir(root):
        if file.endswith('.html'):
            path = os.path.join(root, file)
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '{% macro ui_badge' in content:
                    print(f"FOUND IN {file}")

search()
