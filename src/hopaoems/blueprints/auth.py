
from flask import Blueprint, render_template, request, redirect, url_for, flash
from ..services import auth_service
from ..services.i18n import t

bp = Blueprint('auth', __name__, url_prefix='/auth')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        result = auth_service.login_user(request.form['username'], request.form['password'])
        if result['success']:
            flash(t('auth.login_success'), 'success')
            next_url = request.args.get('next') or url_for('ui.index')
            return redirect(next_url)
        else:
            flash(t(result['message']), 'danger')
            
    return render_template('auth/login.html')

@bp.route('/logout', methods=['POST'])
def logout():
    auth_service.logout_user()
    flash(t('auth.logout_success'), 'info')
    return redirect(url_for('auth.login'))
