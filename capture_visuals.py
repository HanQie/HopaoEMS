import threading
import time
from hopaoems.app_factory import create_app
from hopaoems.services.db import execute_db
from werkzeug.serving import make_server
from playwright.sync_api import sync_playwright

def run_server():
    app = create_app({'TESTING': True, 'DATABASE': 'src/hopaoems/instance/hopaoems_smoke_test.sqlite', 'WTF_CSRF_ENABLED': False})
    # Seed data
    with app.app_context():
        # Clean db and re-seed
        from hopaoems.contracts.smoke_tests import seed_full_scenario
        from hopaoems.services import schema_migrations
        schema_migrations.init_schema()
        ids = seed_full_scenario()
        # Wash a log
        from hopaoems.services import wash_repo
        # Find a log to wash
        from hopaoems.services.db import query_db
        log = query_db("SELECT id FROM production_logs LIMIT 1", one=True)
        if log:
            wash_session_id = wash_repo.create_wash_session('operator')
            wash_repo.add_log_to_wash_session(wash_session_id, log['id'])
            wash_repo.complete_wash_session(wash_session_id, 100, 10, 'operator')

            # We need one unwashed log too to show the two rows
            from hopaoems.services import production_repo
            production_repo.create_log(ids['task_id'], ids['roll_id'], 50.0, 'Second log unwashed', 1, False)

    server = make_server('127.0.0.1', 5005, app)
    server.serve_forever()

t = threading.Thread(target=run_server)
t.daemon = True
t.start()
time.sleep(2) # Wait for server to start

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page()
    
    # Login
    page.goto('http://127.0.0.1:5005/auth/login')
    page.fill('input[name="username"]', 'admin')
    page.fill('input[name="password"]', 'admin')
    page.click('button[type="submit"]')
    page.wait_for_url('http://127.0.0.1:5005/')
    
    # 1. Dashboard Aligned
    page.goto('http://127.0.0.1:5005/production/')
    page.wait_for_selector('.ui-progress')
    page.screenshot(path='c:/Users/JingHu/.gemini/antigravity/brain/af702038-476e-467d-bccd-8913fe9fe194/production_dashboard_aligned.png')
    
    # 2. Test Consume Form
    page.goto('http://127.0.0.1:5005/production/test-consume')
    page.wait_for_selector('form')
    page.screenshot(path='c:/Users/JingHu/.gemini/antigravity/brain/af702038-476e-467d-bccd-8913fe9fe194/test_consume_form.png')
    
    # 3. Log Edit Undo Wash
    # Find the washed log ID
    page.goto('http://127.0.0.1:5005/production/task/1')
    page.wait_for_selector('table')
    # Click the edit button for the washed log (first row)
    page.goto('http://127.0.0.1:5005/production/log/1/edit')
    page.wait_for_selector('form')
    page.screenshot(path='c:/Users/JingHu/.gemini/antigravity/brain/af702038-476e-467d-bccd-8913fe9fe194/log_edit_undo_wash.png')
    
    browser.close()
    print("Screenshots captured.")
