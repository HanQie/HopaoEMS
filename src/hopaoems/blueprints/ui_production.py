
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..services import production_repo, fabric_repo, auth_service
from ..services.i18n import t

bp = Blueprint('ui_production', __name__, url_prefix='/production')

def _prepare_task_vm(task):
    if not task: return None
    t = dict(task)  # copy if it's a sqlite3.Row
    t['printed_length_m'] = t.get('printed') or 0
    t['target_length_m'] = t.get('target') or 0
    
    # Progress Pct
    target = t['target_length_m']
    if target > 0:
        pct = (t['printed_length_m'] / target) * 100
        t['progress_pct'] = round(pct, 1)
    else:
        t['progress_pct'] = 0.0
        
    # Pending Wash Count
    t['pending_wash_count'] = t.get('unwashed_count', 0)
    
    # Can Complete logic (Strict Rules)
    has_logs = t.get('log_count', 0) > 0
    target = t['target_length_m']
    length_met = (t['printed_length_m'] >= target) if target > 0 else has_logs
    
    t['can_complete'] = (
        t['pending_wash_count'] == 0 
        and has_logs 
        and length_met 
        and t.get('status') not in ('done', 'canceled')
    )
    return t

@bp.route('/')
def production_dashboard():
    # Dashboard: KPI + Active Tasks
    from ..services.ui_utils import get_pagination
    page = request.args.get('page', 1, type=int)
    page_size = 50
    offset = (page - 1) * page_size
    
    raw_tasks = production_repo.list_active_tasks_paginated(limit=page_size, offset=offset)
    total = production_repo.count_active_tasks()
    pagination = get_pagination(total, page, page_size)
    
    active_tasks = [_prepare_task_vm(rt) for rt in raw_tasks]
    stats = production_repo.get_dashboard_stats()
    return render_template('production/list.html', 
                           tasks=active_tasks, 
                           stats=stats,
                           pagination=pagination)

@bp.route('/test-consume', methods=['GET', 'POST'])
@auth_service.operator_required
def production_test_consume():
    """Tool for test consumption (from dashboard)."""
    if request.method == 'POST':
        roll_id = request.form.get('roll_id')
        length_str = request.form.get('length')
        note = request.form.get('note')
        mark_empty = request.form.get('mark_empty') == '1'

        if not roll_id or not length_str:
            flash(t('production.error.missing_fields'), 'danger')
            return redirect(url_for('ui_production.production_test_consume'))

        try:
            length_val = float(length_str)
            if length_val <= 0:
                flash(t('production.error.invalid_length'), 'danger')
                return redirect(url_for('ui_production.production_test_consume'))

            fabric_repo.apply_test_consume(
                roll_id=roll_id,
                consumed_length_m=length_val,
                mark_empty=mark_empty,
                note=note,
                actor=g.user['username']
            )
            flash(t('production.test_consume.success'), 'success')
            return redirect(url_for('ui_production.production_dashboard'))
        except ValueError:
            flash(t('production.error.invalid_length'), 'danger')
            return redirect(url_for('ui_production.production_test_consume'))
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('ui_production.production_test_consume'))

    # GET request
    roll_q = request.args.get('roll_q', '').strip()
    rolls = fabric_repo.search_in_stock_rolls(roll_q) if roll_q else fabric_repo.search_in_stock_rolls()
    unit_m = t('common.unit.m')
    roll_options = [(r['id'], f"{r['roll_no']} ({r['fabric_no']}) - {r['length_m']:.1f} {unit_m}") for r in rolls]
    
    return render_template('production/test_consume.html', roll_options=roll_options, roll_q=roll_q)

@bp.route('/task/<int:id>')
def production_task_view(id):
    raw_task = production_repo.get_task_with_progress(id)
    if not raw_task:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_production.production_dashboard'))
    task = _prepare_task_vm(raw_task)
    logs = [dict(log) for log in production_repo.list_logs(id)]
    
    # Attach UI flags
    for log in logs:
        is_locked = production_repo.check_log_lock(log['id'])
        log['is_editable'] = not is_locked
        log['is_deletable'] = not is_locked

    return render_template('production/view.html', task=task, logs=logs)

@bp.route('/task/<int:id>/produce', methods=['GET', 'POST'])
@auth_service.operator_required
def production_task_produce(id):
    raw_task = production_repo.get_task_with_progress(id)
    if not raw_task:
        return "Task not found", 404
    task = _prepare_task_vm(raw_task)

    if request.method == 'POST':
        # Minimal Inputs: roll_id, printed_length, note, roll_depleted
        roll_id = request.form.get('roll_id')
        printed_length = request.form.get('printed_length')
        note = request.form.get('note')
        roll_depleted = request.form.get('roll_depleted') == '1'
        
        if not roll_id or not printed_length:
            flash(t('production.error.missing_fields'), 'danger')
            return redirect(url_for('ui_production.production_task_produce', id=id))
            
        try:
            length = float(printed_length)
            if length <= 0:
                flash(t('production.error.invalid_length'), 'danger')
                return redirect(url_for('ui_production.production_task_produce', id=id), 422)
        except ValueError:
            flash(t('production.error.invalid_length'), 'danger')
            return redirect(url_for('ui_production.production_task_produce', id=id), 422)

        # 2. Fabric and Status Validation
        from ..services.db import query_db
        roll = query_db('''
            SELECT r.*, f.fabric_code 
            FROM rolls r
            JOIN cylinders c ON r.cylinder_id = c.id
            JOIN fabrics f ON c.fabric_id = f.id
            WHERE r.id = ?
        ''', (roll_id,), one=True)
        
        if not roll:
            flash(t('production.error.roll_not_found'), 'danger')
            return redirect(url_for('ui_production.production_task_produce', id=id), 422)
            
        if roll['fabric_code'] != task['fabric_no']:
            flash(t('production.error.roll_mismatch'), 'danger')
            return redirect(url_for('ui_production.production_task_produce', id=id), 422)
            
        if roll['status'] != 'in_stock':
            flash(t('production.error.roll_not_available'), 'danger')
            return redirect(url_for('ui_production.production_task_produce', id=id), 422)

        # 3. Execution
        try:
            log_id = production_repo.create_log(
                id,
                roll_id,
                length,
                note,
                g.user['id'],
                roll_depleted
            )
            flash(t('flash.production.produced'), 'success')
            return redirect(url_for('ui_production.production_task_view', id=id, focus_log_id=log_id) + f'#log-{log_id}')
        except Exception as e:
            flash(f"Error: {e}", 'danger')
            
    # GET: Load rolls grouped by cylinder for Quick Produce (P4-3 Prefix Search)
    roll_q = request.args.get('roll_q', '').strip()
    rolls_grouped = production_repo.list_grouped_rolls_for_task(task['fabric_no'], search_query=roll_q if roll_q else None)
    
    # Format for ui_select optgroups: [(Group Label, [(val, label), ...]), ...]
    roll_options = []
    unit_m = t('common.unit.m')
    for cyl, rolls in rolls_grouped.items():
        sub_options = []
        for r in rolls:
            label = f"{r['roll_no']} ({r['length_m']:.1f} {unit_m})"
            sub_options.append((r['id'], label))
        roll_options.append((cyl or t('common.unknown'), sub_options))
    
    return render_template('production/produce.html', 
                           task=task, 
                           roll_options=roll_options,
                           roll_q=roll_q)

@bp.route('/task/<int:id>/done', methods=['POST'])
@auth_service.operator_required
def production_task_done(id):
    # Aggregated 3-factor verification (Server-Side)
    task_data = production_repo.get_task_with_progress(id)
    if not task_data:
        return "Task not found", 404
        
    task_vm = _prepare_task_vm(task_data)
    
    # Strictly enforce 3 criteria matching UI requirements
    pending_wash = task_vm.get('pending_wash_count', 0)
    has_logs = task_vm.get('log_count', 0) > 0
    met_qty = task_vm.get('printed_length_m', 0) >= task_vm.get('target_length_m', 0)

    if not (pending_wash == 0 and has_logs and met_qty):
        if pending_wash > 0:
            flash(t('production.error.unwashed_blocks_complete'), 'danger')
        elif not has_logs:
            flash(t('production.error.empty_task_complete'), 'danger')
        else:
            flash(t('production.error.incomplete_length'), 'danger')
        return redirect(url_for('ui_production.production_task_view', id=id))
    
    try:
        production_repo.mark_task_done(id)
        flash(t('production.success.task_done'), 'success')
        return redirect(url_for('ui_production.production_dashboard'))
    except Exception as e:
        flash(f"Error: {e}", 'danger')
        return redirect(url_for('ui_production.production_dashboard'))


@bp.route('/log/<int:id>/edit', methods=['GET', 'POST'])
@auth_service.operator_required
def production_log_edit(id):
    log = production_repo.get_log_detail(id)
    if not log:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_production.production_dashboard'))
    
    if request.method == 'POST':
        note = request.form.get('note', '')
        # Only provide new_length if it is present and not empty in the form to allow note-only updates
        new_length = request.form.get('length')
        force_undo = request.form.get('force_undo') == '1'
        
        try:
            # Convert length to float if provided and NOT empty string
            new_length_val = None
            if new_length is not None and str(new_length).strip() != "":
                new_length_val = float(new_length)
            
            success, auto_undo = production_repo.update_log(id, note, new_length_val, force_undo=force_undo)
            
            if auto_undo:
                flash(t('flash.production_log.auto_undo_applied'), 'info')
            else:
                flash(t('flash.production_log.updated'), 'success')
            
            return redirect(url_for('ui_production.production_task_view', id=log['task_id']))
        except ValueError as e:
            flash(t(str(e)), 'danger')
            return render_template('production/log_edit.html', log=log)
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('production/log_edit.html', log=log)
    
    return render_template('production/log_edit.html', log=log)

    return render_template('production/log_edit.html', log=log)

@bp.route('/log/<int:id>/delete', methods=['GET', 'POST'])
@auth_service.operator_required
def production_log_delete(id):
    log = production_repo.get_log_detail(id)
    if not log:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_production.production_dashboard'))
    
    if request.method == 'POST':
        try:
            success, auto_undo = production_repo.delete_log(id)
            
            if auto_undo:
                flash(t('flash.production_log.auto_undo_applied'), 'info')
            
            flash(t('flash.production_log.deleted'), 'success')
            
            return redirect(url_for('ui_production.production_task_view', id=log['task_id']))
        except ValueError as e:
            flash(t(str(e)), 'danger')
            return redirect(url_for('ui_production.production_task_view', id=log['task_id']))
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('ui_production.production_task_view', id=log['task_id']))
            
    # GET: Show Confirmation Page
    return render_template('common/confirm.html',
                           title=t('production.log.delete.title'),
                           message=t('production.log.delete.confirm'),
                           action_url=url_for('ui_production.production_log_delete', id=id),
                           cancel_url=url_for('ui_production.production_task_view', id=log['task_id']))

@bp.route('/log/<int:id>/undo-wash', methods=['GET', 'POST'])
@auth_service.operator_required
def production_log_undo_wash(id):
    log = production_repo.get_log_detail(id)
    if not log:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_production.production_dashboard'))
    
    if request.method == 'POST':
        try:
            production_repo.undo_log_wash(id)
            flash(t('wash.success.undo'), 'success')
            return redirect(url_for('ui_production.production_task_view', id=log['task_id']))
        except Exception as e:
            flash(str(e), 'danger')
            return redirect(url_for('ui_production.production_task_view', id=log['task_id']))
    
    return render_template('common/confirm.html',
                         title=t('production.log.action.undo_wash'),
                         message=t('wash.undo.confirm.desc'),
                         action_url=url_for('ui_production.production_log_undo_wash', id=id),
                         cancel_url=url_for('ui_production.production_task_view', id=log['task_id']))

