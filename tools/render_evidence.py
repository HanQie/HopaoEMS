
import sys
import os
from jinja2 import Environment, FileSystemLoader

# Setup paths
sys.path.append(os.path.join(os.getcwd(), 'src'))

def get_html_evidence():
    templates_path = os.path.join(os.getcwd(), 'src', 'hopaoems', 'templates')
    env = Environment(loader=FileSystemLoader(templates_path))
    
    # Mock globals
    env.globals['t'] = lambda x, **kwargs: f"[{x}]"
    env.globals['url_for'] = lambda endpoint, **kwargs: f"/{endpoint.replace('.', '/')}/{kwargs.get('id', kwargs.get('log_id', ''))}?next={kwargs.get('next', '')}"
    
    # EVIDENCE A: Operator view of washed log
    user_op = {'role': 'operator'}
    log_washed = {
        'id': 99,
        'roll_no': 'R-EVIDENCE',
        'length': 15.5,
        'operator_name': 'Tester',
        'operator_id': 1,
        'washed_at': '2026-02-05',
        'preview_path': 'test.png',
        'created_at': '2026-02-05'
    }
    task = {'id': 10, 'title': 'T10', 'printed': 10, 'target': 50, 'washed': 5, 'to_wash': 5, 'status': 'printing', 'order_no': 'ORD10'}
    
    template = env.get_template('production/view.html')
    try:
        html_rendered = template.render(
            task=task,
            logs=[log_washed],
            g={'user': user_op},
            t=lambda x, **kwargs: f"[{x}]"
        )
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_rendered, 'html.parser')
        # The logs are in a table inside a card.
        # Let's find the tr containing ROLL-EVIDENCE
        rows = soup.find_all('tr')
        for row in rows:
            if 'R-EVIDENCE' in row.get_text():
                tds = row.find_all('td')
                if tds:
                    print("--- EVIDENCE A (OPERATOR) ---")
                    print(tds[-1].prettify())
                
        # EVIDENCE B: Viewer view
        html_rendered_vi = template.render(
            task=task,
            logs=[log_washed],
            g={'user': {'role': 'viewer'}},
            t=lambda x, **kwargs: f"[{x}]"
        )
        soup_vi = BeautifulSoup(html_rendered_vi, 'html.parser')
        rows_vi = soup_vi.find_all('tr')
        for row in rows_vi:
            if 'R-EVIDENCE' in row.get_text():
                tds_vi = row.find_all('td')
                if tds_vi:
                    print("--- EVIDENCE B (VIEWER) ---")
                    print(tds_vi[-1].prettify())
                
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    get_html_evidence()
