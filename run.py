"""
run.py - HopaoEMS server launcher
Handles sys.path so Flask can find the app regardless of CWD.
"""
import sys
import os

# Ensure project root and src are on the path
project_root = os.path.dirname(os.path.abspath(__file__))
src_path = os.path.join(project_root, 'src')
if src_path not in sys.path:
    sys.path.insert(0, src_path)

from hopaoems.app_factory import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
