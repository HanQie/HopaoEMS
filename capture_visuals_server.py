import sys
sys.path.insert(0, 'src')
from hopaoems.app_factory import create_app
from hopaoems.services.db import execute_db
from werkzeug.serving import make_server

app = create_app({'TESTING': True, 'DATABASE': 'src/hopaoems/instance/hopaoems_smoke_test.sqlite', 'WTF_CSRF_ENABLED': False})
with app.app_context():
    from hopaoems.contracts.smoke_tests import seed_full_scenario
    from hopaoems.services import schema_migrations
    schema_migrations.init_schema()
    ids = seed_full_scenario()
    
    from hopaoems.services import wash_repo
    from hopaoems.services.db import query_db
    # Wash all logs so we can see the Complete button
    unwashed = query_db("SELECT id FROM production_logs WHERE washed_at IS NULL")
    if unwashed:
        wash_repo.create_wash_session('VAT-FINAL', [l['id'] for l in unwashed], 1)

server = make_server('127.0.0.1', 5006, app)
print("Server running on 5006")
server.serve_forever()
