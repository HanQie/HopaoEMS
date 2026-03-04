
from hopaoems.app_factory import create_app
import json

app = create_app({'TESTING': True, 'DATABASE': ':memory:', 'WTF_CSRF_ENABLED': False})

def check_keys():
    with app.test_client() as client:
        # 1. Set Lang
        client.get('/i18n/set/zh-TW')
        
        # 2. Get Debug Info
        res = client.get('/__debug/i18n')
        data = res.get_json()
        
        # print(f"Current Locale: {data.get('locale')}")
        
        # 3. Check specific keys manually (simulating what the debug endpoint should show or just accessing config)
        # The debug endpoint returns counts, but currently doesn't return ALL values. 
        # But wait, the user asked to "sample" these 5 keys from the return. 
        # If /__debug/i18n doesn't return values, I can't sample them unless I modify it or just check app config directly.
        # The user said: "get the debug return and sample these 5 keys".
        # Let's see what the debug endpoint actually returns first.
        print("Debug Endpoint Data:", json.dumps(data, indent=2))
        
        # If the debug endpoint assumes I can see keys, maybe I should check app extensions directly 
        # since I am "in" the server code here.
        translations = app.extensions['i18n_translations']['zh-TW']
        keys_to_check = [
            'auth.login_success',
            'auth.logout',
            'nav.fabrics',
            'nav.inks',
            'nav.orders',
            'nav.samples'
        ]
        
        print("\n--- Key Check (zh-TW) ---")
        for k in keys_to_check:
            val = translations.get(k, "MISSING")
            print(f"{k}: '{val}'")

if __name__ == "__main__":
    check_keys()
