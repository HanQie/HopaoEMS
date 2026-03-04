# src/run.py
import sys
import os
from hopaoems.app_factory import create_app

# Enforce Gate Check on Startup (Development)
if __name__ == "__main__":
    # Import and run gates
    from hopaoems.contracts.run_gates import main as run_gates
    print("--- [PRE-FLIGHT] Running Quality Gates ---")
    try:
        run_gates()
    except SystemExit as e:
        if e.code != 0:
            print(f"!!! STARTUP BLOCKED: Quality gates failed. !!!")
            sys.exit(e.code)

    port = int(os.environ.get('PORT', 5000))
    # Check if passed via command line
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            pass
            
    app = create_app()
    app.run(host='0.0.0.0', port=port, debug=True)
