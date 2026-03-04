
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from src.app_factory import create_app
from flask import render_template_string

def verify_t_injection():
    print("Verifying t injection...")
    app = create_app()
    app.config['TESTING'] = True
    
    # 1. Check Globals
    if 't' in app.jinja_env.globals:
        print("✅ PASS: t is in jinja_env.globals")
    else:
        print("❌ FAIL: t is NOT in jinja_env.globals")
        sys.exit(1)
        
    # 2. Check Context Processor
    with app.test_request_context():
        # Render a string that uses t
        try:
            rendered = render_template_string("{{ t('common.actions') }}")
            # We accept "Actions", "操作", or "common.actions" (fallback), as long as it doesn't crash
            print(f"✅ PASS: t() works in template (Output: {rendered})")
        except Exception as e:
            print(f"❌ FAIL: Template render failed: {e}")
            sys.exit(1)

    print("Verification complete.")

if __name__ == "__main__":
    verify_t_injection()
