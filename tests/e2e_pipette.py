import os
import sys
import threading
import time
import io
from PIL import Image
from werkzeug.serving import make_server
from flask import Flask

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))
from hopaoems.app_factory import create_app
from hopaoems.services import db, auth_service

# Configuration
PORT = 5001
BASE_URL = f"http://localhost:{PORT}"
DB_PATH = os.path.join(os.path.dirname(__file__), 'e2e_test.sqlite')

def start_server():
    """Start Flask server in a thread."""
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
        
    app = create_app({
        'TESTING': True,
        'DATABASE': DB_PATH,
        'WTF_CSRF_ENABLED': False # Disable CSRF for E2E simplicity if needed, or handle it
    })
    
    # Create Admin
    with app.app_context():
        # Schema already init by create_app -> init_schema
        # Create admin if not exists (init_schema might have done it)
        user = db.query_db("SELECT * FROM users WHERE username = 'admin'", one=True)
        if not user:
             from werkzeug.security import generate_password_hash
             db.execute_db("INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                           ('admin', generate_password_hash('admin'), 'operator'))
    
    server = make_server('127.0.0.1', PORT, app)
    return server, app

def generate_test_image():
    """Create a 100x100 red image with a green center."""
    path = os.path.join(os.path.dirname(__file__), 'e2e_pipette.png')
    img = Image.new('RGB', (100, 100), color=(255, 0, 0)) # Red
    img.putpixel((50, 50), (0, 255, 0)) # Green dot at center
    img.save(path)
    return path

def run_test():
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("Playwright not installed. Skipping E2E UI verification.")
        print("Run: pip install playwright && playwright install")
        return

    server, app = start_server()
    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()
    
    print(f"Server started at {BASE_URL}")
    img_path = generate_test_image()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True) # Set headless=False to watch
            page = browser.new_page()
            
            # 1. Login
            print("1. Logging in...")
            page.goto(f"{BASE_URL}/auth/login")
            page.fill('input[name="username"]', 'admin')
            page.fill('input[name="password"]', 'admin')
            page.click('button[type="submit"]')
            page.wait_for_url(f"{BASE_URL}/")
            
            # 2. Go to Sample New
            print("2. Navigating to Sample New...")
            page.goto(f"{BASE_URL}/sample/new")
            
            # 3. Upload Image
            print("3. Uploading Image...")
            # Verify hooks exist
            assert page.is_visible('[data-hook="sample-preview-file"]'), "File input missing"
            assert page.is_visible('[data-hook="sample-preview-placeholder"]'), "Placeholder missing"
            assert not page.is_visible('[data-hook="sample-preview-img"]'), "Image should be hidden"
            
            with page.expect_file_chooser() as fc_info:
                page.click('[data-hook="sample-preview-file"]')
            file_chooser = fc_info.value
            file_chooser.set_files(img_path)
            
            # 4. Verify Preview Logic
            print("4. Verifying Preview Logic...")
            # Wait for img to be visible
            page.wait_for_selector('[data-hook="sample-preview-img"]:not([hidden])')
            assert not page.is_visible('[data-hook="sample-preview-placeholder"]'), "Placeholder should be hidden"
            
            # 5. Pipette Click (Green at 50,50)
            print("5. Click to Pipette...")
            img = page.locator('[data-hook="sample-preview-img"]')
            box = img.bounding_box()
            
            # Click exactly in middle (50,50 relative to 100x100 image)
            # Bounding box might be scaled by CSS. 
            # If scaling happens, we assume the JS handles it (which we wrote to do).
            # Let's click center.
            page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
            
            # Verify Display
            time.sleep(0.5)
            display = page.locator('[data-hook="picked-rgb-display"]')
            text = display.text_content()
            print(f"   Picked Text: {text}")
            assert "RGB 0,255,0" in text or "RGB 0, 255, 0" in text, f"Wrong color picked: {text}"
            
            # Verify Button Enabled
            add_btn = page.locator('[data-hook="color-pick-add"]')
            assert not add_btn.is_disabled(), "Add button should be enabled"
            
            # 6. Add Row
            print("6. Adding Row...")
            add_btn.click()
            
            # Verify Row
            row = page.locator('[data-hook="color-corrections-draft-body"] tr').first
            assert row.is_visible(), "Row not added"
            source_text = row.locator('[data-hook="row-source-rgb"]').text_content()
            assert "RGB 0,255,0" in source_text or "RGB 0, 255, 0" in source_text, "Row source incorrect"
            
            # 7. Fill Form & Submit
            print("7. Submitting...")
            page.fill('input[name="sample_no"]', 'E2E-101')
            page.fill('input[name="title"]', 'E2E Test')
            page.click('button[type="submit"]')
            
            # 8. Verify Redirect & Persistence
            print("8. Verifying Persistence...")
            page.wait_for_url(f"{BASE_URL}/sample/")
            assert "E2E-101" in page.content()
            
            # Check thumbnail exists (status 200)
            thumb = page.locator('img[src*="/data/uploads/samples"]').first
            assert thumb.is_visible()
            
            # Verify View Page
            page.click('text=E2E-101')
            page.wait_for_selector('[data-hook="color-corrections-table"]')
            # Check row exists in view
            view_source = page.locator('[data-hook="row-source-rgb"]').first
            v_text = view_source.text_content()
            assert "255" in v_text and "0" in v_text, f"View page row wrong: {v_text}"
            
            print("SUCCESS: E2E Pipette Test Passed!")
            
    except Exception as e:
        print(f"FAILED: {e}")
        import traceback
        traceback.print_exc()
        # Keep server open for debug? No, script should exit.
    finally:
        server.shutdown()
        if os.path.exists(img_path):
            os.remove(img_path)

if __name__ == "__main__":
    run_test()
