from src.app_factory import create_app
import json
import os
from pathlib import Path

def test_sample_backend():
    app = create_app()
    client = app.test_client()
    
    # Ensure src/data exists
    data_dir = Path('src/data')
    data_dir.mkdir(parents=True, exist_ok=True)
    sample_file = data_dir / 'samples.json'

    # 1. Test GET /sample (Initial Empty or Existing)
    print("Testing GET /sample...")
    # For testing reproducibility, let's start with an empty list
    with open(sample_file, 'w', encoding='utf-8') as f:
        json.dump([], f)

    response = client.get('/sample')
    assert response.status_code == 200
    print("✅ GET /sample Success.")
    
    # 2. Test GET /sample/new (Form)
    print("Testing GET /sample/new...")
    response = client.get('/sample/new')
    assert response.status_code == 200
    print("✅ GET /sample/new Success.")

    # 3. Test POST /sample/new
    print("Testing POST /sample/new...")
    sample_data = {
        'sample_name': 'Phase S1 Test Sample',
        'material_code': 'MAT-S1',
        'remark': 'S1 Backend Test'
    }
    # follow_redirects=False to check the 302 redirect
    response = client.post('/sample/new', data=sample_data)
    assert response.status_code == 302
    # Check if redirecting to /sample/1
    assert '/sample/1' in response.location
    print("✅ POST & Redirect Success.")
    
    # 4. Test GET /sample/1 (The redirected page)
    print("Testing GET /sample/1...")
    response = client.get('/sample/1')
    assert response.status_code == 200
    print("✅ GET /sample/1 Success.")
    
    # 5. Test GET /sample/999 (Non-existent)
    print("Testing GET /sample/999 (Non-existent)...")
    response = client.get('/sample/999')
    assert response.status_code == 200 # Requirement: 200 + placeholder render
    print("✅ GET /sample/999 Success (200 OK).")

    # 6. Verify src/data/samples.json
    print("Verifying src/data/samples.json...")
    with open(sample_file, 'r', encoding='utf-8') as f:
        samples = json.load(f)
        assert len(samples) > 0
        assert samples[0]['sample_name'] == 'Phase S1 Test Sample'
        assert samples[0]['id'] == 1
    print("✅ samples.json content verified.")

if __name__ == "__main__":
    try:
        test_sample_backend()
        print("\nAll Backend Tests PASSED!")
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        exit(1)
