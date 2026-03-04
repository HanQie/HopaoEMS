import io
from src.app_factory import create_app
import json
import os

def test_sample_upload_temp_api():
    # Set TESTING=True to enable X-Hopao-Role header hook
    app = create_app({"TESTING": True})
    client = app.test_client()
    
    # We use 'operator' role to bypass permission checks if any
    headers = {"X-Hopao-Role": "operator"}

    print("--- Diagnostic Test: POST /sample/upload-temp ---")
    
    # Use 'file' as the field name as per new requirement
    test_file_content = b"fake image data contents for testing"
    data = {
        'file': (io.BytesIO(test_file_content), "test_diagnostic.jpg")
    }
    
    response = client.post('/sample/upload-temp', 
                           data=data, 
                           headers=headers, 
                           content_type='multipart/form-data')
    
    print(f"Response Status: {response.status_code}")
    body_text = response.get_data(as_text=True)
    print(f"Response Body: {body_text}")
    
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    
    res_json = json.loads(body_text)
    assert "temp_id" in res_json, "Response missing temp_id"
    assert "preview_url" in res_json, "Response missing preview_url"
    
    preview_url = res_json["preview_url"]
    print(f"✅ POST Upload Success. Preview URL: {preview_url}")

    print(f"\n--- Diagnostic Test: GET {preview_url} ---")
    # Test if the preview URL is actually accessible and returns the file
    response = client.get(preview_url, headers=headers)
    
    print(f"Response Status: {response.status_code}")
    print(f"Mimetype: {response.mimetype}")
    
    assert response.status_code == 200, f"Expected 200 for preview URL, got {response.status_code}"
    assert response.mimetype.startswith("image/"), f"Expected image mimetype, got {response.mimetype}"
    assert response.data == test_file_content, "File content mismatch"
    
    print("✅ GET Preview Success. File integrity verified.")

    # 3. Test Failure: Missing file field
    print("\n--- Diagnostic Test: Missing file field ---")
    response = client.post('/sample/upload-temp', data={}, headers=headers)
    assert response.status_code == 400
    print(f"✅ Correctly handled missing file field (400). Body: {response.get_data(as_text=True)}")

    # 4. Test Failure: Empty file
    print("\n--- Diagnostic Test: Empty file ---")
    data_empty = {
        'file': (io.BytesIO(b""), "empty.jpg")
    }
    response = client.post('/sample/upload-temp', data=data_empty, headers=headers, content_type='multipart/form-data')
    assert response.status_code == 400
    print(f"✅ Correctly handled empty file (400). Body: {response.get_data(as_text=True)}")

if __name__ == "__main__":
    try:
        test_sample_upload_temp_api()
        print("\n🎉 ALL SAMPLE UPLOAD DIAGNOSTIC TESTS PASSED!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
