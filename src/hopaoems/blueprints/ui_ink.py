
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..services import ink_repo, auth_service
from ..services.i18n import t

bp = Blueprint('ui_ink', __name__, url_prefix='/ink')

@bp.route('/')
@auth_service.login_required
def ink_list():
    from ..services.ui_utils import get_pagination
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    page_size = 50
    offset = (page - 1) * page_size
    
    inks = ink_repo.list_inks_paginated(limit=page_size, offset=offset, q=q)
    total = ink_repo.count_inks(q=q)
    pagination = get_pagination(total, page, page_size)
    
    return render_template('ink/list.html', inks=inks, q=q, pagination=pagination)

@bp.route('/new', methods=['GET', 'POST'])
@auth_service.operator_required
def ink_new():
    if request.method == 'POST':
        ink_repo.create_ink(
            request.form['date'],
            request.form['type'],
            request.form['color'],
            request.form['qty'],
            request.form.get('note')
        )
        flash(t('common.created_successfully'), 'success')
        return redirect(url_for('ui_ink.ink_list'))
    return render_template('ink/form.html')

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@auth_service.operator_required
def ink_edit(id):
    ink = ink_repo.get_ink(id)
    if request.method == 'POST':
        ink_repo.update_ink(
            id,
            request.form['date'],
            request.form['type'],
            request.form['color'],
            request.form['qty'],
            request.form.get('note')
        )
        flash(t('common.updated_successfully'), 'success')
        return redirect(url_for('ui_ink.ink_list'))
    return render_template('ink/form.html', ink=ink)

    return render_template('ink/form.html', ink=ink)

@bp.route('/<int:id>/delete', methods=['GET', 'POST'])
@auth_service.operator_required
def ink_delete(id):
    if request.method == 'POST':
        ink_repo.delete_ink(id)
        flash(t('common.deleted_successfully'), 'success')
        return redirect(url_for('ui_ink.ink_list'))

    # GET: Show Confirmation Page
    return render_template('common/confirm.html',
                           title=t('ink.delete.title'),
                           message=t('common.confirm_delete'),
                           action_url=url_for('ui_ink.ink_delete', id=id),
                           cancel_url=url_for('ui_ink.ink_list'))
