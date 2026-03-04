
import sys
import os
contract_dir = os.path.dirname(os.path.abspath('src/hopaoems/contracts/smoke_tests.py'))
src_path = os.path.abspath(os.path.join(contract_dir, '..', '..'))
sys.path.insert(0, src_path)
from hopaoems.app_factory import create_app
from hopaoems.services import schema_migrations
from hopaoems.services.db import execute_db, query_db

app = create_app({'TESTING': True, 'DATABASE': ':memory:', 'WTF_CSRF_ENABLED': False})
with app.app_context():
    schema_migrations.init_schema()
    exec(open('src/hopaoems/contracts/smoke_tests.py', encoding='utf-8').read())
    ids = seed_full_scenario()
    client = app.test_client()
    client.post('/auth/login', data={'username': 'admin', 'password': 'admin'})
    res = client.post('/production/task/1/produce', data={
        'roll_id': '1',
        'printed_length': '12.5',
        'roll_depleted': '1',
        'note': 'Smoke Test'
    }, follow_redirects=True)
    print(f'STATUS: {res.status_code}')
    print(f'ALERT IN DATA: {b"alert" in res.data}')
    if b"alert" in res.data:
        idx = res.data.find(b"alert")
        print(f'CONTEXT: {res.data[idx-50:idx+50]}')
    
    # Also check if it's hitting a 422 or something
    res_raw = client.post('/production/task/1/produce', data={
        'roll_id': '1',
        'printed_length': '12.5',
        'roll_depleted': '1',
        'note': 'Smoke Test'
    }, follow_redirects=False)
    print(f'RAW STATUS: {res_raw.status_code}')
    if res_raw.status_code != 302:
        print(f'ERROR BODY: {res_raw.get_data(as_text=True)[:500]}')
