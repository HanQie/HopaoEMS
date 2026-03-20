
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory, g
from werkzeug.utils import secure_filename
from ..services import sample_repo, auth_service
from ..services.i18n import t

def _process_image_upload(file):
    """Handle image upload: resize to max 2048px, convert to PNG, return filename."""
    if not file or not file.filename:
        return None
        
    from PIL import Image
    import time
    
    try:
        # 1. Load from stream (avoids saving original to disk)
        img = Image.open(file)
        
        # 2. Resize if exceeds 2048px on long edge
        max_dim = 2048
        w, h = img.size
        if w > max_dim or h > max_dim:
            if w > h:
                new_w = max_dim
                new_h = int(h * (max_dim / w))
            else:
                new_h = max_dim
                new_w = int(w * (max_dim / h))
            # NEAREST preserves original pixels better for color picking as requested
            img = img.resize((new_w, new_h), Image.NEAREST)
            
        # 3. Mode normalization (Ensure RGB)
        if img.mode != 'RGB':
            img = img.convert('RGB')
            
        # 4. Save as PNG
        filename = f"{int(time.time())}_{secure_filename(file.filename)}"
        filename = os.path.splitext(filename)[0] + ".png"
        
        upload_dir = current_app.config['SAMPLES_UPLOAD_DIR']
        os.makedirs(upload_dir, exist_ok=True)
        
        target_path = os.path.join(upload_dir, filename)
        img.save(target_path, "PNG")
        return filename
    except Exception as e:
        print(f"Image processing error: {e}")
        return False # Indicator for failure

bp = Blueprint('ui_sample', __name__, url_prefix='/sample')

@bp.route('/')
def sample_list():
    from ..services.ui_utils import get_pagination
    q = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    page_size = 50
    offset = (page - 1) * page_size
    
    samples = [dict(s) for s in sample_repo.list_samples_paginated_enriched(q=q, limit=page_size, offset=offset)]
    total = sample_repo.count_samples(q=q)
    pagination = get_pagination(total, page, page_size)
    
    view = request.args.get('view', 'table')
    return render_template('sample/list.html', samples=samples, q=q, view=view, pagination=pagination)

@bp.route('/new', methods=['GET', 'POST'])
@auth_service.login_required
def sample_new():
    if request.method == 'POST':
        if g.user['role'] != 'operator':
            from flask import abort
            abort(403)
            
        sample_no = request.form.get('sample_no')
        title = request.form.get('title')
        fabric_no = request.form.get('fabric_no')
        date_received = request.form.get('date_received')
        sampled_date = request.form.get('sampled_date')
        version = request.form.get('version')
        printing_environment = request.form.get('printing_environment')
        printing_file_name = request.form.get('printing_file_name')
        remark = request.form.get('remark')
        
        preview_path = None
        if 'preview_image' in request.files:
            file = request.files['preview_image']
            if file and file.filename:
                preview_path = _process_image_upload(file)
                if preview_path is False:
                    flash(t('sample.error.resize_failed'), 'danger')
                    return redirect(request.url), 422
        sample_id = sample_repo.create_sample(
            sample_no=sample_no,
            title=title,
            fabric_no=fabric_no,
            date_received=date_received,
            sampled_date=sampled_date,
            preview_path=preview_path,
            version=version,
            printing_environment=printing_environment,
            printing_file_name=printing_file_name,
            remark=remark
        )

        # Process Color Corrections (Step 1.2: Aligned getlist)
        rs = request.form.getlist('cc_r')
        gs = request.form.getlist('cc_g')
        bs = request.form.getlist('cc_b')
        modes = request.form.getlist('cc_mode')
        ls = request.form.getlist('cc_l')
        as_ = request.form.getlist('cc_a')
        b2s = request.form.getlist('cc_b2')
        notes = request.form.getlist('cc_note')

        rows_to_save = []
        def get_val(lst, i, default=None):
            return lst[i] if i < len(lst) else default

        for i in range(len(rs)):
            if rs[i] == '': continue
            try:
                rows_to_save.append({
                    'rgb_r': int(rs[i]),
                    'rgb_g': int(gs[i]) if i < len(gs) else 0,
                    'rgb_b': int(bs[i]) if i < len(bs) else 0,
                    'target_mode': get_val(modes, i, 'note'),
                    'target_l': float(ls[i]) if i < len(ls) and ls[i] else None,
                    'target_a': float(as_[i]) if i < len(as_) and as_[i] else None,
                    'target_b': float(b2s[i]) if i < len(b2s) and b2s[i] else None,
                    'target_note': get_val(notes, i)
                })
            except (ValueError, IndexError):
                continue
        
        if rows_to_save:
            sample_repo.replace_color_corrections(sample_id, rows_to_save)
        
        flash(t('common.created_successfully'), 'success')
        return redirect(url_for('ui_sample.sample_list'))
    
    return render_template('sample/form.html')

@bp.route('/<int:id>/color-corrections/save', methods=['POST'])
@auth_service.operator_required
def sample_save_corrections(id):
    sample = sample_repo.get_sample(id)
    if not sample:
        from flask import abort
        abort(404)
        
    # Process Color Corrections (Replace-all strategy)
    rs = request.form.getlist('cc_r')
    gs = request.form.getlist('cc_g')
    bs = request.form.getlist('cc_b')
    modes = request.form.getlist('cc_mode')
    ls = request.form.getlist('cc_l')
    as_ = request.form.getlist('cc_a')
    b2s = request.form.getlist('cc_b2')
    notes = request.form.getlist('cc_note')

    rows_to_save = []
    def get_val(lst, i, default=None):
        return lst[i] if i < len(lst) else default

    for i in range(len(rs)):
        if rs[i] == '': continue
        try:
            rows_to_save.append({
                'rgb_r': int(rs[i]),
                'rgb_g': int(gs[i]) if i < len(gs) else 0,
                'rgb_b': int(bs[i]) if i < len(bs) else 0,
                'target_mode': get_val(modes, i, 'note'),
                'target_l': float(ls[i]) if i < len(ls) and ls[i] else None,
                'target_a': float(as_[i]) if i < len(as_) and as_[i] else None,
                'target_b': float(b2s[i]) if i < len(b2s) and b2s[i] else None,
                'target_note': get_val(notes, i)
            })
        except (ValueError, IndexError):
            continue
    
    sample_repo.replace_color_corrections(id, rows_to_save)
    flash(t('common.updated_successfully'), 'success')
            
    return redirect(url_for('ui_sample.sample_view', id=id))

@bp.route('/<int:id>/pick-color', methods=['POST'])
@auth_service.operator_required
def sample_pick_color(id):
    sample = sample_repo.get_sample(id)
    if not sample:
        return "Sample not found", 404
        
    px = request.form.get('pick_x', type=int)
    py = request.form.get('pick_y', type=int)
    note = request.form.get('note')
    
    try:
        (red, green, blue), hex_val = sample_repo.pick_pixel_color(sample['preview_path'], px, py)
        sample_repo.add_full_color_correction(
            sample_id=id,
            pick_x=px,
            pick_y=py,
            rgb_r=red,
            rgb_g=green,
            rgb_b=blue,
            hex_val=hex_val,
            target_mode='note',
            target_note=note
        )
        flash(t('sample.pick_color.success'), 'success')
    except Exception as e:
        print(f"Pick Color Error: {e}")
        flash(t('sample.pick_color.error'), 'error')

    return redirect(url_for('ui_sample.sample_view', id=id))



@bp.route('/<int:id>/color-corrections/clear', methods=['POST'])
@auth_service.operator_required
def color_corrections_clear(id):
    sample_repo.clear_color_corrections(id)
    flash(t('sample.color_corrections.cleared'), 'success')
    return redirect(url_for('ui_sample.sample_view', id=id))

@bp.route('/<int:id>')
def sample_view(id):
    from ..services.db import query_db
    sample = sample_repo.get_sample(id)
    if not sample:
        from flask import abort
        abort(404)
    color_maps = sample_repo.list_color_maps(id)
    
    stats = {
        'color_pick_count': len(color_maps),
        'version': sample['version'] or 1
    }
    
    return render_template('sample/view.html', sample=sample, color_maps=color_maps,
                           stats=stats)

@bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@auth_service.operator_required
def sample_edit(id):
    sample = sample_repo.get_sample(id)
    if not sample:
        return "Sample not found", 404
        
    if request.method == 'POST':
        sample_no = request.form.get('sample_no')
        title = request.form.get('title')
        fabric_no = request.form.get('fabric_no')
        date_received = request.form.get('date_received')
        sampled_date = request.form.get('sampled_date')
        version = request.form.get('version')
        printing_environment = request.form.get('printing_environment')
        printing_file_name = request.form.get('printing_file_name')
        remark = request.form.get('remark')
        
        # Process Color Corrections (Same logic as New)
        rs = request.form.getlist('cc_r')
        gs = request.form.getlist('cc_g')
        bs = request.form.getlist('cc_b')
        modes = request.form.getlist('cc_mode')
        ls = request.form.getlist('cc_l')
        as_ = request.form.getlist('cc_a')
        b2s = request.form.getlist('cc_b2')
        notes = request.form.getlist('cc_note')

        rows_to_save = []
        def get_val(lst, i, default=None):
            return lst[i] if i < len(lst) else default

        for i in range(len(rs)):
            if rs[i] == '': continue
            try:
                rows_to_save.append({
                    'rgb_r': int(rs[i]),
                    'rgb_g': int(gs[i]) if i < len(gs) else 0,
                    'rgb_b': int(bs[i]) if i < len(bs) else 0,
                    'target_mode': get_val(modes, i, 'note'),
                    'target_l': float(ls[i]) if i < len(ls) and ls[i] else None,
                    'target_a': float(as_[i]) if i < len(as_) and as_[i] else None,
                    'target_b': float(b2s[i]) if i < len(b2s) and b2s[i] else None,
                    'target_note': get_val(notes, i)
                })
            except (ValueError, IndexError):
                continue
        
        # Always replace, even if empty (clears details)
        sample_repo.replace_color_corrections(id, rows_to_save)

        # Handle Image Upload (Optional on Edit)
        preview_path = sample['preview_path']
        if 'preview_image' in request.files:
            file = request.files['preview_image']
            if file and file.filename:
                new_path = _process_image_upload(file)
                if new_path is False:
                    flash(t('sample.error.resize_failed'), 'danger')
                    return redirect(request.url), 422
                if new_path:
                    # Optional: Could delete old file here if desired
                    preview_path = new_path

        sample_repo.update_sample(
            id=id,
            sample_no=sample_no,
            title=title,
            fabric_no=fabric_no,
            date_received=date_received,
            sampled_date=sampled_date,
            preview_path=preview_path, # Passed to update
            version=version,
            printing_environment=printing_environment,
            printing_file_name=printing_file_name,
            remark=remark
        )
        flash(t('common.updated_successfully'), 'success')
        return redirect(url_for('ui_sample.sample_view', id=id))

    color_maps = sample_repo.list_color_maps(id)
    return render_template('sample/form.html', sample=sample, color_maps=color_maps)

@bp.route('/<int:id>/delete', methods=['GET', 'POST'])
@auth_service.operator_required
def sample_delete(id):
    sample = sample_repo.get_sample(id)
    if not sample:
        from flask import abort
        abort(404)
        
    if request.method == 'POST':
        try:
            sample_repo.delete_sample_safe(id)
            flash(t('sample.toast.deleted'), 'success')
            return redirect(url_for('ui_sample.sample_list'))
        except ValueError as e:
            flash(t(str(e)), 'error')
            return redirect(url_for('ui_sample.sample_view', id=id))
            
    # GET: Show confirmation
    return render_template('sample/delete_confirm.html', sample=sample)

