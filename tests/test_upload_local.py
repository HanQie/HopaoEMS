
import os, sys, io
sys.path.insert(0, os.path.abspath('src'))
from hopaoems.app_factory import create_app
from hopaoems.services.db import query_db

app = create_app()
client = app.test_client()

# Login
client.post('/auth/login', data={'username': 'admin', 'password': 'admin'})

# Post Sample
data = {
    'sample_no': 'S-TEST-UPLOAD',
    'title': 'Test Upload',
    'preview_image': (io.BytesIO(b"fake image data"), 'test.jpg')
}
res = client.post('/sample/new', data=data, content_type='multipart/form-data', follow_redirects=True)
print(f"Status: {res.status_code}")

with app.app_context():
    sample = query_db("SELECT * FROM samples WHERE sample_no='S-TEST-UPLOAD'", one=True)
    if sample:
        print(f"ID: {sample['id']} PATH: {sample['preview_path']}")
    else:
        print("Record NOT found")
