from src.app_factory import create_app
import json

def test_i18n_api():
    app = create_app()
    client = app.test_client()
    
    # 1. Test GET
    print("Testing GET /api/i18n/seeds...")
    response = client.get('/api/i18n/seeds')
    assert response.status_code == 200
    data = response.get_json()
    keys_count = len(data)
    print(f"✅ Success. Keys count: {keys_count}")
    
    # 2. Test POST
    # We'll try to update a test key or add one
    test_key = "test.api_update"
    payload = {
        test_key: {"en": "API Update Test", "zh": "API 更新測試"}
    }
    # Add existing keys to the payload to not wipe them out (the API sorts and writes what it gets)
    # Actually my API implementation wipes and rewrites based on payload.
    # To be safe in a test, we should probably merge or just check if it works.
    # Let's just send the whole thing back with one extra key.
    
    merged_payload = data.copy()
    merged_payload[test_key] = payload[test_key]
    
    print(f"Testing POST /api/i18n/seeds with new key: {test_key}...")
    post_response = client.post('/api/i18n/seeds', json=merged_payload)
    assert post_response.status_code == 200
    assert post_response.get_json()["ok"] == True
    print("✅ POST Success.")
    
    # Verify file update
    print("Verifying file content...")
    with open('src/i18n/seed.en.json', 'r', encoding='utf-8') as f:
        en_json = json.load(f)
        assert en_json[test_key] == "API Update Test"
    print(f"✅ Verified {test_key} in seed.en.json")
    
    # Cleanup (remove the test key)
    print("Cleaning up...")
    del merged_payload[test_key]
    client.post('/api/i18n/seeds', json=merged_payload)
    print("✅ Cleanup Success.")

if __name__ == "__main__":
    test_i18n_api()
