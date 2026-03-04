import sys
sys.path.insert(0, 'src')
from hopaoems.app_factory import create_app
from hopaoems.services.db import query_db, execute_db

app = create_app()
with app.test_client() as client:
    with app.app_context():
        # Login
        client.post('/auth/login', data={'username': 'operator', 'password': 'operator'})
        
        # Check task status before
        task = query_db('SELECT * FROM production_tasks WHERE id = 1', one=True)
        print('Task before: status=' + task['status'])
        
        # Wash all logs
        execute_db('UPDATE production_logs SET washed_at = CURRENT_TIMESTAMP WHERE task_id = 1')
        
        # Try done
        res = client.post('/production/task/1/done', follow_redirects=False)
        print('Done response: ' + str(res.status_code))
        
        # Check task after
        task = query_db('SELECT * FROM production_tasks WHERE id = 1', one=True)
        print('Task after done: status=' + task['status'])
        
        # Try close
        res = client.post('/order/1/close', follow_redirects=False)
        print('Close response: ' + str(res.status_code))
        if res.status_code != 302:
            print('Close error: ' + res.get_data(as_text=True)[:500])
        
        # Check order
        order = query_db('SELECT * FROM orders WHERE id = 1', one=True)
        print('Order after close: status=' + order['status'])
