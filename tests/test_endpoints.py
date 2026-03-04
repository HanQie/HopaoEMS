from src.app_factory import create_app

app = create_app()
with app.test_client() as client:
    resp_root = client.get('/')
    print('GET /', resp_root.status_code)
    resp_order = client.get('/order')
    print('GET /order', resp_order.status_code)
    resp_health = client.get('/api/health')
    print('GET /api/health', resp_health.status_code, resp_health.get_json())
