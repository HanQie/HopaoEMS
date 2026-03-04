from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..services import wash_repo, auth_service, ui_utils
from ..services.i18n import t

bp = Blueprint('ui_wash', __name__, url_prefix='/wash')

@bp.route('/', methods=['GET'])
def wash_list():
    data = wash_repo.get_wash_list_data()
    return render_template('wash/list.html', 
                         groups=data['groups'], 
                         stats=data['stats'])

@bp.route('/register/<vat_code>', methods=['GET'])
@auth_service.operator_required
def wash_register(vat_code):
    data = wash_repo.get_wash_list_data()
    # Find the specific group
    group = next((g for g in data['groups'] if g['vat_code'] == vat_code), None)
    
    if not group:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_wash.wash_list'))
        
    return render_template('wash/register.html', group=group)

@bp.route('/commit', methods=['POST'])
@auth_service.operator_required
def wash_commit():
    vat_code = request.form.get('vat_code')
    log_ids = request.form.getlist('log_ids')
    
    if not log_ids:
        flash(t('flash.wash_session.nothing_selected'), 'warning')
        return redirect(url_for('ui_wash.wash_list'))
        
    try:
        # Extra verification (optional but safer)
        # 1. log_ids must all belong to this vat_code
        # 2. log_ids must all be unwashed
        # (REPO handles DB integrity anyway)
        
        wash_repo.create_wash_session(vat_code, log_ids, g.user['id'])
        flash(t('flash.wash_session.created'), 'success')
        
    except Exception as e:
        flash(str(e), 'danger')
        
    return redirect(url_for('ui_wash.wash_list'))

@bp.route('/history', methods=['GET'])
def wash_history():
    from ..services.ui_utils import get_pagination
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    page_size = 50
    offset = (page - 1) * page_size
    
    sessions = wash_repo.list_visible_sessions_paginated(search_query=q, limit=page_size, offset=offset)
    total = wash_repo.count_visible_sessions(search_query=q)
    pagination = get_pagination(total, page, page_size)
    
    # Attach logs for expansion
    for s in sessions:
        s['logs'] = wash_repo.get_session_logs(s['id'])
        # Also need tone_idx for session header style?
        s['tone_idx'] = ui_utils.get_vat_tone_idx(s['vat_code'])
        
    return render_template('wash/history.html', sessions=sessions, q=q, pagination=pagination)

@bp.route('/session/<int:session_id>', methods=['GET'])
def wash_session_view(session_id):
    session = wash_repo.get_session_by_id(session_id)
    if not session:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_wash.wash_history'))
    
    logs = wash_repo.get_session_logs(session_id)
    session['logs'] = logs
    session['tone_idx'] = ui_utils.get_vat_tone_idx(session['vat_code'])
    
    return render_template('wash/detail.html', session=session)
    
@bp.route('/revoke/<int:session_id>', methods=['GET', 'POST'])
@auth_service.operator_required
def wash_revoke(session_id):
    if request.method == 'POST':
         try:
             wash_repo.revoke_session(session_id)
             flash(t('wash.success.revoked'), 'success')
         except Exception as e:
             flash(str(e), 'danger')
         return redirect(url_for('ui_wash.wash_history'))
         
    # GET: Confirm page
    return render_template('common/confirm.html',
                         title=t('wash.action.revoke'),
                         message=t('wash.confirm.revoke_message'),
                         action_url=url_for('ui_wash.wash_revoke', session_id=session_id),
                         cancel_url=url_for('ui_wash.wash_history'))

@bp.route('/log/<int:log_id>/undo', methods=['GET', 'POST'])
@auth_service.operator_required
def wash_log_undo(log_id):
    # GET: Fetch log first to check status
    log = wash_repo.get_log_for_undo(log_id)
    if not log:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_wash.wash_list'))
        
    # Fool-proof: Cannot undo if not washed
    if log['washed_at'] is None:
         flash(t('wash.undo.error.already_unwashed'), 'warning')
         return redirect(url_for('ui_wash.wash_list'))

    if request.method == 'POST':
        try:
            wash_repo.undo_log(log_id)
            flash(t('wash.success.undo'), 'success')
        except Exception as e:
            flash(str(e), 'danger')
        
        # Redirect to 'next' if provided, otherwise to wash list
        next_url = request.args.get('next') or request.form.get('next') or url_for('ui_wash.wash_list')
        return redirect(next_url)
    
    # GET: Build confirmation message with log details
    details = f"{t('wash.undo.vat')}: {log['vat_code']}\n"
    details += f"{t('wash.undo.roll')}: {log['roll_no']}\n"
    details += f"{t('wash.undo.length')}: {log['length']}{t('common.unit.m')}\n"
    if log['sample_title']:
        details += f"{t('wash.undo.sample')}: {log['sample_title']}"
    
    next_url = request.args.get('next', '')
    
    return render_template('common/confirm.html',
                         title=t('wash.action.undo'),
                         message=t('wash.undo.confirm.desc') + '\n\n' + details,
                         action_url=url_for('ui_wash.wash_log_undo', log_id=log_id, next=next_url),
                         cancel_url=next_url or url_for('ui_wash.wash_list'))
