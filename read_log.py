import sys
try:
    with open('debug_smoke.log', 'r', encoding='utf-16') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            if 'DEBUG: t(' in line:
                print(line.strip())
except Exception as e:
    print(e)
