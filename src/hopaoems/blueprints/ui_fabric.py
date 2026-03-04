from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..services import fabric_repo, auth_service, ui_utils
from ..services.i18n import t

bp = Blueprint('ui_fabric', __name__, url_prefix='/fabric')

def parse_width_to_mm(width_string):
    if not width_string:
        return None
    width_string = str(width_string).strip().lower()
    if width_string.endswith('cm'):
        val = float(width_string.replace('cm', '').strip())
        return int(val * 10)
    elif width_string.endswith('mm'):
        val = float(width_string.replace('mm', '').strip())
        return int(val)
    else:
        try:
            val = float(width_string)
            return int(val * 10)
        except ValueError:
            return None

@bp.route('/')
@auth_service.login_required
def fabric_list():
    """Fabric List Page - Shows all fabrics with card/table toggle"""
    from ..services.db import query_db
    from ..services.ui_utils import get_pagination
    
    q = request.args.get('q', '').strip().lower()
    page = request.args.get('page', 1, type=int)
    view = request.args.get('view', 'table') # grid, table
    
    page_size = 24 if view == 'grid' else 50
    offset = (page - 1) * page_size
    
    # Get paginated fabrics
    fabrics = [dict(f) for f in fabric_repo.list_fabrics_paginated(limit=page_size, offset=offset, q=q)]
    total = fabric_repo.count_fabrics(q=q)
    pagination = get_pagination(total, page, page_size)
    
    # Add stats to each fabric
    for fabric in fabrics:
        # Calculate In Stock metrics (status='in_stock')
        inventory_result = query_db('''
            SELECT 
                COALESCE(SUM(r.length_m), 0) as total_len,
                COUNT(DISTINCT r.cylinder_id) as cyl_count,
                COUNT(r.id) as roll_count
            FROM rolls r
            JOIN cylinders c ON r.cylinder_id = c.id
            WHERE c.fabric_id = ? AND r.status = 'in_stock'
        ''', (fabric['id'],), one=True)
        
        fabric['total_inventory'] = round(inventory_result['total_len'], 1) if inventory_result else 0
        fabric['in_stock_cylinders'] = inventory_result['cyl_count'] if inventory_result else 0
        fabric['in_stock_rolls'] = inventory_result['roll_count'] if inventory_result else 0
    
    return render_template('fabric/list.html', 
                           fabrics=fabrics,
                           q=q,
                           view=view,
                           pagination=pagination)


@bp.route('/explorer')
@auth_service.login_required
def fabric_explorer():
    fabric_id = request.args.get('fabric_id', type=int)
    q = request.args.get('q', '').strip().lower()
    
    # If no fabric_id, redirect to list (or handle appropriately)
    if not fabric_id:
        return redirect(url_for('ui_fabric.fabric_list'))
    
    fabric = fabric_repo.get_fabric(fabric_id)
    if not fabric:
        flash(t('common.not_found'), 'danger')
        return redirect(url_for('ui_fabric.fabric_list'))
        
    # Fetch all cylinders and rolls for this fabric
    cylinders = fabric_repo.list_cylinders(fabric_id)
    
    # Group rolls by cylinder
    # Structure: [{'cylinder': c, 'rolls': [], 'stats': {...}}]
    cylinder_groups = []
    
    total_inventory_m = 0
    total_rolls_count = 0
    
    for cyl in cylinders:
        rolls = [dict(r) for r in fabric_repo.list_rolls_by_cylinder(cyl['id'])]
        
        # Apply Search Filter
        # If q matches cylinder_no: Show ALL rolls (context)
        # If q matches roll_no: Show matching rolls
        # Unless cylinder matches, only show Matching Rolls
        
        cyl_match = q and (q in cyl['cylinder_no'].lower())
        
        if q:
            if cyl_match:
                # Keep all rolls, as user searched for the VAT
                pass 
            else:
                # Filter rolls
                rolls = [r for r in rolls if q in r['roll_no'].lower()]
            
            # If neither cylinder matches nor any rolls match, skip this group
            if not cyl_match and not rolls:
                continue
        
        # Recalculate stats for the filtered set (or unfiltered full set)
        # Verify strictness: stats should reflect VISIBLE or TOTAL?
        # Usually total inventory on top reflects REALITY. Group stats reflect GROUP.
        # But if we filter, maybe we just show the group.
        # Let's keep existing stats logic from DB for consistency, or re-calc based on rolls?
        # The prompt says: "Result: only show matching cylinder/roll".
        # Displaying stats: It's better to show stats of the filtered view if possible, or just hide them.
        # But `get_cylinder_stats` hits DB. Let's use that for now, as it's cleaner.
        stats = fabric_repo.get_cylinder_stats(cyl['id'])
        
        cylinder_groups.append({
            'cylinder': cyl,
            'rolls': rolls,
            'stats': stats
        })
        
        if stats:
            total_inventory_m += stats['in_stock_sum_length']
            # Only count total rolls in the whole fabric, regardless of search?
            # Or reflect search? "Fabric Overview" usually implies global stats.
            # Let's accumulate global stats from DB-fetched stats (which are total).
            # This ensures top-level stats remain correct even if view is filtered.
            total_rolls_count += stats['roll_count']
            
    # Fabric Summary Stats (Always Global for the Fabric)
    fabric_stats = {
        'total_inventory': round(total_inventory_m, 1),
        'cylinder_count': len(cylinders), # Total cylinders
        'roll_count': total_rolls_count   # Total rolls
    }
    
    # If search active, maybe we want to show filtered count?
    # But user requirement is about "display filtered results". Top header usually stays global.

    return render_template('fabric/explorer.html', 
                           fabric=fabric,
                           cylinder_groups=cylinder_groups,
                           stats=fabric_stats,
                           q=q)


@bp.route('/new', methods=['GET', 'POST'])
@auth_service.operator_required
def fabric_new():
    """P0: Minimal fabric creation for Stock-In workflow"""
    if request.method == 'POST':
        fabric_code = request.form['fabric_code'].strip()
        
        # Check for duplicate
        existing = fabric_repo.get_fabric_by_code(fabric_code)
        if existing:
            flash(t('fabric.error.duplicate_code'), 'danger')
            return render_template('fabric/new.html', 
                                 fabric_code=fabric_code,
                                 next_url=request.args.get('next', url_for('ui_fabric.stock_in_form')))
        
        # Create fabric with P0 fields
        try:
            new_fabric = fabric_repo.create_fabric(
                fabric_code=fabric_code,
                width_mm=parse_width_to_mm(request.form.get('width_mm')),
                gram_per_yard=float(request.form['gram_per_yard']),
                material_type=request.form['material_type'],
                remark=request.form.get('remark') or None
            )
            flash(t('common.created_successfully'), 'success')
            
            return redirect(url_for('ui_fabric.fabric_list'))
        except Exception as e:
            flash(str(e), 'danger')
            return render_template('fabric/new.html',
                                 fabric_code=fabric_code,
                                 next_url=request.args.get('next', url_for('ui_fabric.stock_in_form')))
    
    # GET: Show form
    return render_template('fabric/new.html',
                         next_url=request.args.get('next', url_for('ui_fabric.stock_in_form')))


@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@auth_service.operator_required
def fabric_edit(id):
    fabric = fabric_repo.get_fabric(id)
    if request.method == 'POST':
        fabric_repo.update_fabric(
            id=id,
            fabric_code=request.form['fabric_code'].strip(),
            width_mm=parse_width_to_mm(request.form.get('width_mm')),
            gram_per_yard=float(request.form['gram_per_yard']),
            material_type=request.form['material_type'],
            remark=request.form.get('remark') or None
        )
        flash(t('common.updated_successfully'), 'success')
        return redirect(url_for('ui_fabric.fabric_explorer', fabric_id=id))
    return render_template('fabric/new.html', fabric=fabric, fabric_code=fabric['fabric_code'], next_url=url_for('ui_fabric.fabric_explorer', fabric_id=id))

@bp.route('/cylinder/<int:id>/edit', methods=['GET', 'POST'])
@auth_service.operator_required
def cylinder_edit(id):
    cylinder = fabric_repo.get_cylinder(id)
    if request.method == 'POST':
        fabric_repo.update_cylinder(id, request.form['cylinder_no'].strip())
        flash(t('common.updated_successfully'), 'success')
        return redirect(url_for('ui_fabric.fabric_explorer', fabric_id=cylinder['fabric_id'], cylinder_id=id))
    return render_template('fabric/cylinder_form.html', cylinder=cylinder)

@bp.route('/roll/<int:id>/edit', methods=['GET', 'POST'])
@auth_service.operator_required
def roll_edit(id):
    roll = fabric_repo.get_roll(id)
    if request.method == 'POST':
        # Simple edit (no qty change here to avoid logic overlap with adjust_stock)
        # But for '改' requirement, we allow editing roll_no and remark
        from datetime import datetime
        now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        execute_db('UPDATE rolls SET roll_no = ?, remark = ?, updated_at = ? WHERE id = ?', 
                   (request.form['roll_no'].strip(), request.form.get('remark'), now_str, id))
        commit()
        flash(t('common.updated_successfully'), 'success')
        # Resolve back to explorer
        cylinder = fabric_repo.get_cylinder(roll['cylinder_id'])
        return redirect(url_for('ui_fabric.fabric_explorer', fabric_id=cylinder['fabric_id'], cylinder_id=roll['cylinder_id']))
    return render_template('fabric/roll_form.html', roll=roll)

# @bp.route('/<int:id>/cylinder/new', methods=['POST'])
# @auth_service.operator_required
# def cylinder_new(id):
#     fabric_repo.create_cylinder(id, request.form['cylinder_no'])
#     flash(t('common.created_successfully'), 'success')
#     return redirect(url_for('ui_fabric.fabric_view', id=id))

# @bp.route('/cylinder/<int:id>')
# @auth_service.login_required
# def cylinder_view(id):
#     tab = request.args.get('tab', 'in_stock')
#     cylinder = fabric_repo.get_cylinder(id)
#     if not cylinder:
#         return "Cylinder not found", 404
#         
#     stats = fabric_repo.get_cylinder_stats(id)
#     
#     rolls = []
#     history = []
#     if tab == 'history':
#         history = fabric_repo.list_cylinder_history(id)
#     else:
#         rolls = fabric_repo.list_rolls_by_cylinder(id, status=tab)
#         
#     return render_template('fabric/cylinder_view.html', 
#                            cylinder=cylinder,
#                            rolls=rolls,
#                            history=history,
#                            stats=stats,
#                            selected_tab=tab)

# @bp.route('/cylinder/<int:id>/roll/new', methods=['POST'])
# @auth_service.operator_required
# def roll_new(id):
#     fabric_repo.create_roll(
#         id,
#         request.form['roll_no'],
#         float(request.form.get('length_m', 0)),
#         float(request.form.get('weight_kg', 0)),
#         request.form.get('remark')
#     )
#     flash(t('common.created_successfully'), 'success')
#     return redirect(url_for('ui_fabric.cylinder_view', id=id))

# @bp.route('/roll/<int:id>')
# @auth_service.login_required
# def roll_view(id):
#     roll = fabric_repo.get_roll(id)
#     if not roll:
#         return "Roll not found", 404
#     history = fabric_repo.list_roll_history(id)
#     return render_template('fabric/roll_view.html', roll=roll, history=history)

# @bp.route('/roll/<int:id>/edit', methods=['GET', 'POST'])
# @auth_service.operator_required
# def roll_edit(id):
#     roll = fabric_repo.get_roll(id)
#     if request.method == 'POST':
#         # Logic to update basic info (remark, etc) - Repo needs update function
#         # For now, minimal stub to pass route check
#         pass
#     return render_template('fabric/roll_form.html', roll=roll)

@bp.route('/roll/<int:id>/adjust-stock', methods=['GET', 'POST'])
@auth_service.operator_required
def roll_adjust_stock(id):
    roll = fabric_repo.get_roll(id)
    if not roll:
        return "Roll not found", 404

    if request.method == 'POST':
        new_length_m = request.form.get('new_length_m')
        note = request.form.get('note')
        
        # 1. Basic validation
        if not new_length_m or note is None:
            flash(t('common.error.missing_fields'), 'danger')
            return render_template('fabric/roll_adjust_stock.html', roll=roll), 422
            
        try:
            length = float(new_length_m)
            if length < 0:
                flash(t('fabric.error.negative_length'), 'danger')
                return render_template('fabric/roll_adjust_stock.html', roll=roll), 422
        except ValueError:
            flash(t('fabric.error.invalid_length'), 'danger')
            return render_template('fabric/roll_adjust_stock.html', roll=roll), 422

        # 2. Execution
        try:
            fabric_repo.adjust_roll_stock(
                id,
                length,
                source='manual_adjust',
                note=note,
                user_name=g.user['username']
            )
            flash(t('common.updated_successfully'), 'success')
            return redirect(url_for('ui_fabric.roll_view', id=id))
        except Exception as e:
            flash(f"Error: {e}", 'danger')
            return render_template('fabric/roll_adjust_stock.html', roll=roll), 422
            
    return render_template('fabric/roll_adjust_stock.html', roll=roll)

    return render_template('fabric/roll_adjust_stock.html', roll=roll)

@bp.route('/roll/<int:id>/deplete', methods=['GET', 'POST'])
@auth_service.operator_required
def roll_deplete(id):
    if request.method == 'POST':
        try:
            fabric_repo.deplete_roll(id, 'manual_adjust', 'Marked as depleted', g.user['username'])
            flash(t('common.updated_successfully'), 'success')
        except Exception as e:
            flash(str(e), 'danger')
        return redirect(request.referrer or url_for('ui_fabric.fabric_explorer'))

    # GET: Show Confirmation Page
    roll = fabric_repo.get_roll(id)
    if not roll:
        return "Roll not found", 404
        
    return render_template('common/confirm.html',
                           title=t('fabric.actions.deplete'),
                           message=f"{t('fabric.roll_no')}: {roll['roll_no']}",
                           action_url=url_for('ui_fabric.roll_deplete', id=id),
                           action_label=t('common.confirm'),
                           variant='neutral',
                           back_url=request.referrer or url_for('ui_fabric.fabric_explorer'))

@bp.route('/stock-in', methods=['GET'])
@auth_service.operator_required
def stock_in_form():
    fabric_id = request.args.get('fabric_id', type=int)
    cylinder_id = request.args.get('cylinder_id', type=int)
    cylinder_no = request.args.get('cylinder_no', '')
    tab = request.args.get('tab', 'in_stock')
    
    # Resolve missing context if reached via cylinder link
    if cylinder_id and not fabric_id:
        cyl = fabric_repo.get_cylinder(cylinder_id)
        if cyl:
            fabric_id = cyl['fabric_id']
            cylinder_no = cyl['cylinder_no']

    fabrics = fabric_repo.list_fabrics()
    pre_selected_fabric = None
    fabric_cylinders = []
    if fabric_id:
        pre_selected_fabric = fabric_repo.get_fabric(fabric_id)
        fabric_cylinders = fabric_repo.list_cylinders(fabric_id)

    return render_template('fabric/stock_in_form.html', 
                           fabrics=fabrics,
                           fabric_id=fabric_id,
                           cylinder_id=cylinder_id,
                           cylinder_no=cylinder_no,
                           tab=tab,
                           pre_selected_fabric=pre_selected_fabric,
                           fabric_cylinders=fabric_cylinders)

@bp.route('/stock-in/commit', methods=['POST'])
@auth_service.operator_required
def stock_in_commit():
    fabric_id = request.form.get('fabric_id', type=int)
    cylinder_id = request.form.get('cylinder_id', type=int)
    cylinder_no = request.form.get('cylinder_no')
    cylinder_mode = request.form.get('cylinder_mode', 'new')
    tab = request.form.get('tab', 'in_stock')
    
    if cylinder_mode == 'existing' and request.form.get('existing_cylinder_id'):
        cylinder_id = request.form.get('existing_cylinder_id', type=int)
        cyl = fabric_repo.get_cylinder(cylinder_id)
        if cyl:
            cylinder_no = cyl['cylinder_no']
            
    if not fabric_id or not cylinder_no:
        flash(t('common.error.missing_fields'), 'danger')
        return redirect(url_for('ui_fabric.stock_in_form'))
        
    fabric = fabric_repo.get_fabric(fabric_id)
    if not fabric or not fabric['yard_weight_gyd'] or fabric['yard_weight_gyd'] <= 0:
        flash(t('fabric.stock_in.error.missing_gyd'), 'danger')
        return redirect(url_for('ui_fabric.stock_in_form', fabric_id=fabric_id, cylinder_no=cylinder_no))
        
    gram_per_yard = fabric['yard_weight_gyd']
    roll_rows = []
    
    # Process dynamic rows (JS may add beyond the initial 10)
    roll_no_keys = sorted(
        [k for k in request.form.keys() if k.startswith('roll_no_')],
        key=lambda k: int(k.split('_')[-1]) if k.split('_')[-1].isdigit() else 0
    )
    for key in roll_no_keys:
        i = key.replace('roll_no_', '')
        r_no = request.form.get(f'roll_no_{i}', '').strip()
        w_kg_str = request.form.get(f'weight_kg_{i}', '').strip()
        remark = request.form.get(f'remark_{i}', '').strip() or None
        
        # Skip empty rows
        if not r_no and not w_kg_str:
            continue
            
        # Error on partial rows
        if (r_no and not w_kg_str) or (not r_no and w_kg_str):
            flash(t('common.error.missing_fields') + f" (Row {i})", 'danger')
            return redirect(url_for('ui_fabric.stock_in_form', fabric_id=fabric_id, cylinder_no=cylinder_no))
            
        try:
            w_kg = float(w_kg_str)
            if w_kg <= 0:
                raise ValueError
        except ValueError:
            flash(t('fabric.error.invalid_length') + f" (Row {i})", 'danger')
            return redirect(url_for('ui_fabric.stock_in_form', fabric_id=fabric_id, cylinder_no=cylinder_no))
            
        # Calculation: length_m = (weight_kg * 1000 / gram_per_yard) * 0.9144
        # 1 yard = 0.9144 meters
        weight_g = w_kg * 1000.0
        length_yd = weight_g / gram_per_yard
        length_m = length_yd * 0.9144
        
        roll_rows.append({
            'roll_no': r_no,
            'length_m': round(length_m, 1),
            'remark': remark
        })
        
    if not roll_rows:
        flash(t('common.error.missing_fields'), 'danger')
        return redirect(url_for('ui_fabric.stock_in_form', fabric_id=fabric_id, cylinder_no=cylinder_no))
        
    submitted_rolls = [r['roll_no'] for r in roll_rows]
    seen = set()
    dupes_in_batch = []
    for r in submitted_rolls:
        if r in seen:
            dupes_in_batch.append(r)
        seen.add(r)
    
    if dupes_in_batch:
        flash(t('fabric.error.duplicate_roll_no_batch', roll_nos=', '.join(dupes_in_batch)), 'danger')
        return redirect(url_for('ui_fabric.stock_in_form', fabric_id=fabric_id, cylinder_no=cylinder_no))

    cyl_id_for_check = cylinder_id
    if not cyl_id_for_check and cylinder_no:
        from ..services.db import query_db
        cyl = query_db('SELECT id FROM cylinders WHERE fabric_id = ? AND cylinder_no = ?', (fabric_id, cylinder_no), one=True)
        if cyl:
            cyl_id_for_check = cyl['id']
            
    if cyl_id_for_check:
        from ..services.db import query_db
        existing_rolls = query_db('SELECT roll_no FROM rolls WHERE cylinder_id = ? AND roll_no IN (' + ','.join(['?']*len(submitted_rolls)) + ')', [cyl_id_for_check] + submitted_rolls)
        if existing_rolls:
            dupes_in_db = [r['roll_no'] for r in existing_rolls]
            flash(t('fabric.error.duplicate_roll_no_db', roll_nos=', '.join(dupes_in_db)), 'danger')
            return redirect(url_for('ui_fabric.stock_in_form', fabric_id=fabric_id, cylinder_no=cylinder_no))
        
    fabric_repo.create_stock_in_batch(fabric_id, cylinder_no, roll_rows, user_name=g.user['username'])
    flash(t('common.created_successfully'), 'success')
    
    return redirect(url_for('ui_fabric.fabric_explorer', 
                           fabric_id=fabric_id, 
                           cylinder_id=cylinder_id, 
                           tab=tab) + '#rolls-top')


@bp.route('/stock-in/template.xlsx')
@auth_service.operator_required
def stock_in_template_xlsx():
    """Download a static XLSX template for bulk stock-in."""
    from flask import send_from_directory, current_app
    import os
    
    template_dir = os.path.join(current_app.root_path, 'static', 'templates')
    return send_from_directory(
        template_dir,
        'fabric_stockin_template.xlsx',
        as_attachment=True,
        download_name='stock_in_template.xlsx'
    )


@bp.route('/stock-in/import-xlsx', methods=['POST'])
@auth_service.operator_required
def stock_in_import_xlsx():
    """Parse a bulk stock-in XLSX file and return rows/errors as JSON."""
    from flask import jsonify
    try:
        import openpyxl
    except ImportError:
        return jsonify({'rows': [], 'errors': [{'row': 0, 'field': 'file', 'message': 'openpyxl not installed'}]}), 500

    file = request.files.get('xlsx_file')
    if not file or not file.filename:
        return jsonify({'rows': [], 'errors': [{'row': 0, 'field': 'file', 'message': t('common.error.missing_fields')}]}), 400

    try:
        wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        ws = wb.active

        headers = [str(c.value or '').strip().lower() for c in next(ws.iter_rows(min_row=1, max_row=1))]
        expected = ['roll_no', 'weight_kg', 'remark']
        if headers[:2] != expected[:2]:
            return jsonify({
                'rows': [],
                'errors': [{'row': 1, 'field': 'header', 'message': t('fabric.intake.import.error.invalid_header')}]
            }), 422

        rows = []
        errors = []
        seen_roll_nos = set()

        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            roll_no = str(row[0] or '').strip() if len(row) > 0 else ''
            weight_raw = str(row[1] or '').strip() if len(row) > 1 else ''
            remark = str(row[2] or '').strip() if len(row) > 2 else ''

            if not roll_no and not weight_raw:
                continue  # skip empty rows

            if not roll_no:
                errors.append({'row': row_idx, 'field': 'roll_no',
                                'message': t('fabric.intake.import.error.missing_roll_no', row=row_idx)})
                continue

            try:
                weight = float(weight_raw)
                if weight <= 0:
                    raise ValueError
            except (ValueError, TypeError):
                errors.append({'row': row_idx, 'field': 'weight_kg',
                                'message': t('fabric.intake.import.error.invalid_weight', row=row_idx)})
                continue

            if roll_no in seen_roll_nos:
                errors.append({'row': row_idx, 'field': 'roll_no',
                                'message': t('fabric.intake.import.error.duplicate_roll_no', row=row_idx, value=roll_no)})
                continue

            seen_roll_nos.add(roll_no)
            rows.append({'roll_no': roll_no, 'weight_kg': weight, 'remark': remark})

        return jsonify({'rows': rows, 'errors': errors})

    except Exception as e:
        return jsonify({'rows': [], 'errors': [{'row': 0, 'field': 'file', 'message': str(e)}]}), 500

@bp.route('/cylinder/<int:id>/delete', methods=['GET', 'POST'])
@auth_service.operator_required
def cylinder_delete(id):
    if request.method == 'POST':
        try:
            fabric_repo.delete_cylinder_cascade(id)
            flash(t('common.deleted_successfully'), 'success')
            return redirect(url_for('ui_fabric.fabric_explorer'))
        except ValueError as e:
            flash(str(e), 'danger')
            return redirect(request.referrer or url_for('ui_fabric.fabric_explorer'))

    # Confirm Page
    cylinder = fabric_repo.get_cylinder(id)
    stats = fabric_repo.get_cylinder_stats(id)
    # Check production usage for early warning?
    is_used = fabric_repo.check_cylinder_has_production(id)
    # Though we block in POST, UI can warn or disable.
    
    message_parts = [
        t('fabric.cylinder_no') + ': ' + cylinder['cylinder_no'],
        t('fabric.rolls') + ': ' + str(stats['roll_count']),
        t('fabric.confirm.delete_items')
    ]
    return render_template('common/confirm.html',
        title=t('common.confirm_delete'),
        message='. '.join(message_parts),
        action_url=url_for('ui_fabric.cylinder_delete', id=id),
        action_label=t('common.delete'),
        variant='danger',
        back_url=request.referrer or url_for('ui_fabric.fabric_explorer'))

@bp.route('/roll/<int:id>/delete', methods=['GET', 'POST'])
@auth_service.operator_required
def roll_delete(id):
    if request.method == 'POST':
        fid = request.form.get('fabric_id')
        cid = request.form.get('cylinder_id')
        try:
            fabric_repo.delete_roll_safe(id)
            flash(t('common.deleted_successfully'), 'success')
        except ValueError as e:
            flash(str(e), 'danger')
        return redirect(url_for('ui_fabric.fabric_explorer', fabric_id=fid, cylinder_id=cid) + '#rolls-top')

    roll = fabric_repo.get_roll(id)
    return render_template('common/confirm.html',
        title=t('common.confirm_delete'),
        message=f"{t('fabric.roll_no')}: {roll['roll_no']}",
        action_url=url_for('ui_fabric.roll_delete', id=id),
        hidden_fields={
            'fabric_id': request.args.get('fabric_id'),
            'cylinder_id': request.args.get('cylinder_id')
        },
        back_url=url_for('ui_fabric.fabric_explorer', 
                        fabric_id=request.args.get('fabric_id'), 
                        cylinder_id=request.args.get('cylinder_id')))


@bp.route('/roll/<int:id>/history')
@auth_service.login_required
def roll_history(id):
    roll = fabric_repo.get_roll(id)
    if not roll:
        flash(t('fabric.error.roll_not_found'), 'danger')
        return redirect(url_for('ui_fabric.fabric_explorer'))
        
    history = fabric_repo.list_roll_history(id)
    return render_template('fabric/roll_history.html', roll=roll, history=history)
