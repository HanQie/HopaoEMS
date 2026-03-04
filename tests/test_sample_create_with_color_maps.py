"""
Integration test for creating a sample with color maps in a single step.
"""
import io
import json
from src.app_factory import create_app
from src.services import sample_repo

def test_sample_create_with_color_maps():
    app = create_app({"TESTING": True})
    client = app.test_client()
    headers = {"X-Hopao-Role": "operator"}

    # 1. Upload temp file
    test_image = b"\xFF\xD8\xFF\xDB\x00\x43\x00\x08" # dummy jpeg
    resp = client.post('/sample/upload-temp', 
                       data={'file': (io.BytesIO(test_image), 'test.jpg')},
                       headers=headers,
                       content_type='multipart/form-data')
    assert resp.status_code == 200
    res_json = json.loads(resp.get_data(as_text=True))
    temp_id = res_json['temp_id']

    # 2. Prepare color maps JSON
    color_maps = [
        {
            "pick_x": 100, "pick_y": 100, 
            "rgb_r": 255, "rgb_g": 0, "rgb_b": 0, "hex": "#ff0000",
            "replace_lab": "50,10,10", "replace_device_color": "C0M100Y100K0", "note": "Red spot"
        },
        {
            "pick_x": 200, "pick_y": 200, 
            "rgb_r": 0, "rgb_g": 255, "rgb_b": 0, "hex": "#00ff00",
            "replace_lab": "80,-50,50", "replace_device_color": "C100M0Y100K0", "note": "Green spot"
        }
    ]

    # 3. Create sample
    payload = {
        'name': 'Batch Color Test',
        'temp_id': temp_id,
        'color_maps_json': json.dumps(color_maps)
    }
    
    resp = client.post('/sample/new', data=payload, headers=headers)
    assert resp.status_code == 302
    
    # 4. Verify data
    new_id = int(resp.headers['Location'].split('/')[-1])
    sample = sample_repo.get_sample(new_id)
    assert sample['name'] == 'Batch Color Test'
    
    maps = sample_repo.get_color_maps(new_id)
    assert len(maps) == 2
    assert maps[0]['rgb_r'] in [255, 0]
    assert maps[1]['replace_lab'] in ["50,10,10", "80,-50,50"]
    
    print(f"✅ Sample {new_id} created with {len(maps)} color maps.")

if __name__ == "__main__":
    import sys
    sys.path.insert(0, 'src')
    test_sample_create_with_color_maps()
