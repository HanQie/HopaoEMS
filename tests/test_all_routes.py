import sys
import os

# Ensure src is in path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from src.app_factory import create_app
from src.services.db import get_conn
from werkzeug.security import generate_password_hash

def ensure_test_user():
    """Ensure a test user exists and return credentials."""
    username = "test_operator_auto"
    password = "password123"
    
    try:
        conn = get_conn()
        # Check if user exists
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        
        if not user:
            print(f"Creating test user {username}...")
            # Do NOT provide ID, let autoincrement handle it
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), "operator")
            )
            conn.commit()
        else:
            # If user exists, we assume password is correct
            pass
             
        conn.close()
        return username, password
    except Exception as e:
        print(f"User setup failed: {e}")
        # Fallback to default operator if migration ran
        return "operator", "operator"

def main():
    app = create_app()
    app.config['TESTING'] = True
    
    username, password = ensure_test_user()
    
    # Define operator-only routes that should be tested with operator role
    operator_only_routes = {
        '/order/new',
        '/sample/new',
        '/fabric/new',
        '/production/new',
        '/ink/new'
    }
    
    endpoints = [
        '/',
        '/order',
        '/order/new',
        '/order/1',
        '/order/edit/1',
        '/sample',
        '/sample/new',
        '/sample/1',
        '/fabric',
        '/fabric/new',
        '/fabric/1',
        '/fabric/stock',
        '/production',
        '/production/new',
        '/production/1',
        '/production/wash-list',
        '/ink',
        '/ink/new',
        '/settings',
        '/settings/translations'
    ]

    with app.test_client() as client:
        # Login as operator
        print(f"Logging in as {username}...")
        resp = client.post('/login', data={'username': username, 'password': password}, follow_redirects=True)
        if resp.status_code != 200 or b'Sign In' in resp.data: 
            if b'Sign In' in resp.data:
                print("Login FAILED (remains on login page)")
                # Try default operator just in case
                if username != "operator":
                    print("Retrying with default operator...")
                    client.post('/login', data={'username': 'operator', 'password': 'operator'}, follow_redirects=True)
        
        failed = False
        for endpoint in endpoints:
            try:
                resp = client.get(endpoint)
                status_text = "PASS"
                if resp.status_code == 500:
                    status_text = "FAIL (500 Internal Server Error)"
                    print(f"GET {endpoint:<30} {status_text}")
                    # Print first few lines of error if possible
                    if b'Traceback' in resp.data:
                         print("   Target template likely crashed.")
                    failed = True
                    continue

                if b'NameError' in resp.data or b'TemplateSyntaxError' in resp.data:
                     status_text = "FAIL (Template Error Rendered)"
                     print(f"GET {endpoint:<30} {status_text}")
                     failed = True
                     continue

                if resp.status_code != 200:
                    if resp.status_code == 302:
                        location = resp.headers.get('Location', '')
                        # Whitelist expected redirects
                        is_expected_redirect = False
                        if '/production/wash-list' in endpoint: is_expected_redirect = True
                        elif '/ink' in endpoint: is_expected_redirect = True
                        elif any(x in endpoint for x in ['/order/', '/sample/', '/fabric/', '/production/']) and endpoint.split('/')[-1].isdigit():
                            is_expected_redirect = True # ID missing, redirect to list is okay for this test
                        
                        if is_expected_redirect:
                            status_text = f"PASS (302) -> {location}"
                        else:
                            status_text = f"FAIL (302) -> {location}"
                            failed = True
                    elif resp.status_code == 404:
                         # Whitelist detail routes where ID might be missing
                         if '/1' in endpoint:
                            status_text = "PASS (404 - Expected for ID 1)"
                         else:
                            status_text = "FAIL (404 Not Found)"
                            failed = True
                    elif resp.status_code == 403:
                        status_text = "FAIL (403 - Operator should have access)"
                        failed = True
                    else:
                        status_text = f"FAIL ({resp.status_code})"
                        failed = True
                
                print(f"GET {endpoint:<30} {status_text}")
            except Exception as e:
                print(f"GET {endpoint:<30} ERROR: {e}")
                failed = True
        
        if failed:
            sys.exit(1)
        else:
            print("All tests passed.")
            sys.exit(0)

if __name__ == "__main__":
    main()
