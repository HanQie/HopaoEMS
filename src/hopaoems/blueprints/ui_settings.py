from flask import Blueprint, render_template
from ..services import auth_service, db

bp = Blueprint('ui_settings', __name__, url_prefix='/settings')

@bp.route('/')
@auth_service.login_required
def settings_list():
    # Placeholder for settings. Currently static.
    return render_template('settings/list.html')

@bp.route('/activity')
@auth_service.operator_required
def activity_log():
    activities = db.query_db('''
        SELECT a.*, u.username as operator_name
        FROM audit_logs a
        LEFT JOIN users u ON a.operator_id = u.id
        ORDER BY a.timestamp DESC
        LIMIT 100
    ''')
    return render_template('settings/activity.html', activities=activities)
