
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..services import order_repo, fabric_repo, sample_repo, auth_service
from ..services.i18n import t

bp = Blueprint('ui_order', __name__, url_prefix='/order')

@bp.route('/')
@auth_service.login_required
def order_list():
    from ..services.ui_utils import get_pagination
    status = request.args.get('status', 'active')
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    page_size = 20
    offset = (page - 1) * page_size
    
    orders = order_repo.list_orders_paginated(status_filter=status, q=q, limit=page_size, offset=offset)
    total = order_repo.count_orders(status_filter=status, q=q)
    pagination = get_pagination(total, page, page_size)
    
    # Calculate due_in_days
    from datetime import date
    today = date.today()
    updated_orders = []
    for o in orders:
        o_dict = dict(o)
        if o_dict.get('due_date'):
            try:
                # Assuming due_date is string 'YYYY-MM-DD'
                due = date.fromisoformat(o_dict['due_date'])
                o_dict['due_in_days'] = (due - today).days
            except Exception:
                o_dict['due_in_days'] = None
        else:
            o_dict['due_in_days'] = None
        updated_orders.append(o_dict)

    return render_template('order/list.html', 
                           orders=updated_orders, 
                           status=status, 
                           q=q,
                           pagination=pagination)

@bp.route('/new', methods=['GET', 'POST'])
@auth_service.operator_required
def order_new():
    if request.method == 'POST':
        items = []
        for i in range(20): # increased max items
            f_no = request.form.get(f'items[{i}][fabric_no]')
            if f_no:
                items.append({
                    'fabric_no': f_no,
                    'sample_id': request.form.get(f'items[{i}][sample_id]'),
                    'qty': float(request.form.get(f'items[{i}][qty]') or 0),
                    'note': request.form.get(f'items[{i}][note]')
                })
        
        try:
            order_repo.create_order(
                request.form['order_no'],
                request.form.get('received_date'),
                request.form.get('due_date'),
                request.form.get('note'),
                items
            )
            flash(t('common.created_successfully'), 'success')
            return redirect(url_for('ui_order.order_list'))
        except ValueError as e:
            flash(t(str(e)), 'danger')
        except Exception as e:
            flash(f"Error: {e}", 'danger')
            
    fabrics = fabric_repo.list_fabrics()
    samples = sample_repo.list_samples()
    fabric_options = [(f['fabric_code'], f['fabric_code']) for f in fabrics]
    sample_options = [(s['id'], f"{s['sample_no']} - {s['title']}") for s in samples]
    
    return render_template('order/form.html', fabrics=fabrics, samples=samples, 
                           fabric_options=fabric_options, sample_options=sample_options)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@auth_service.operator_required
def order_edit(id):
    order = order_repo.get_order(id)
    if not order:
        return "Order not found", 404

    if request.method == 'POST':
        items = []
        for i in range(20):
            f_no = request.form.get(f'items[{i}][fabric_no]')
            if f_no:
                item_id = request.form.get(f'items[{i}][id]')
                items.append({
                    'id': int(item_id) if item_id else None,
                    'fabric_no': f_no,
                    'sample_id': request.form.get(f'items[{i}][sample_id]'),
                    'qty': float(request.form.get(f'items[{i}][qty]') or 0),
                    'note': request.form.get(f'items[{i}][note]')
                })
        
        try:
            order_repo.update_order(
                id,
                request.form['order_no'],
                request.form.get('received_date'),
                request.form.get('due_date'),
                request.form.get('note'),
                items
            )
            flash(t('common.updated_successfully'), 'success')
            return redirect(url_for('ui_order.order_view', id=id))
        except ValueError as e:
            flash(t(str(e)), 'danger')
            # Fall through to re-render form with error
        except Exception as e:
            flash(f"Error: {e}", 'danger')

    fabrics = fabric_repo.list_fabrics()
    samples = sample_repo.list_samples()
    fabric_options = [(f['fabric_code'], f['fabric_code']) for f in fabrics]
    sample_options = [(s['id'], f"{s['sample_no']} - {s['title']}") for s in samples]
    
    return render_template('order/form.html', order=order, fabrics=fabrics, samples=samples, 
                           fabric_options=fabric_options, sample_options=sample_options)

@bp.route('/<int:id>')
@auth_service.login_required
def order_view(id):
    order = order_repo.get_order(id)
    if not order:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_order.order_list'))
    
    # Compute summary aggregates for dossier cards
    tasks = order.get('tasks', [])
    printing_count = sum(1 for t_ in tasks if t_.get('status') == 'printing')
    done_count = sum(1 for t_ in tasks if t_.get('status') == 'done')
    canceled_count = sum(1 for t_ in tasks if t_.get('status') == 'canceled')
    total_unwashed_count = sum(t_.get('unwashed_count', 0) for t_ in tasks)
    total_unwashed_length = sum(t_.get('total_printed', 0) or 0 for t_ in tasks) - sum(t_.get('total_washed', 0) or 0 for t_ in tasks)
    if total_unwashed_length < 0:
        total_unwashed_length = 0
    
    # Deletion safety check
    can_delete, delete_reason = order_repo.can_delete_order(id)
    
    return render_template('order/view.html', order=order,
                           printing_count=printing_count,
                           done_count=done_count,
                           canceled_count=canceled_count,
                           total_unwashed_count=total_unwashed_count,
                           total_unwashed_length=total_unwashed_length,
                           can_delete=can_delete,
                           delete_reason=delete_reason)

@bp.route('/task/<int:task_id>/reopen', methods=['POST'])
@auth_service.operator_required
def task_reopen(task_id):
    try:
        order_id = order_repo.reopen_task(task_id)
        flash(t('order.task.reopen.success'), 'success')
        return redirect(url_for('ui_order.order_view', id=order_id))
    except ValueError as e:
        flash(t(str(e)), 'danger')
        return redirect(request.referrer or url_for('ui_order.order_list'))

@bp.route('/item/<int:item_id>/delete', methods=['GET', 'POST'])
@auth_service.operator_required
def order_item_delete(item_id):
    item = order_repo.get_order_item(item_id)
    if not item:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_order.order_list'))
    
    order_id = item['order_id']
    if request.method == 'POST':
        try:
            order_repo.delete_order_item(item_id)
            flash(t('common.deleted_successfully'), 'success')
            return redirect(url_for('ui_order.order_view', id=order_id))
        except ValueError as e:
            flash(t(str(e)), 'danger')
            return redirect(url_for('ui_order.order_view', id=order_id))
        except Exception as e:
            flash(f"Error: {e}", 'danger')
            return redirect(url_for('ui_order.order_view', id=order_id))
            
    return render_template('common/confirm.html',
                           title=t('order.item.delete.confirm_title'),
                           message=t('order.item.delete.confirm_body'),
                           action_url=url_for('ui_order.order_item_delete', item_id=item_id),
                           cancel_url=url_for('ui_order.order_view', id=order_id),
                           confirm_variant='danger')

@bp.route('/<int:id>/delete', methods=['GET', 'POST'])
@auth_service.operator_required
def order_delete(id):
    order = order_repo.get_order(id)
    if not order:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_order.order_list'))
    
    can_del, reason = order_repo.can_delete_order(id)
    if request.method == 'POST':
        if not can_del:
            flash(t(reason or 'order.delete.not_allowed_has_logs'), 'danger')
            return redirect(url_for('ui_order.order_view', id=id))
        
        try:
            order_repo.delete_order(id)
            flash(t('common.deleted_successfully'), 'success')
            return redirect(url_for('ui_order.order_list'))
        except Exception as e:
            flash(f"Error: {e}", 'danger')
            return redirect(url_for('ui_order.order_view', id=id))
            
    if not can_del:
        flash(t(reason or 'order.delete.not_allowed_has_logs'), 'warning')
        return redirect(url_for('ui_order.order_view', id=id))

    return render_template('common/confirm.html',
                           title=t('order.delete.confirm_title'),
                           body=t('order.delete.confirm_body'),
                           confirm_url=url_for('ui_order.order_delete', id=id),
                           cancel_url=url_for('ui_order.order_view', id=id),
                           confirm_variant='danger')
