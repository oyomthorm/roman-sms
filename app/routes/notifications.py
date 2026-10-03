from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, jsonify)
from flask_login import login_required, current_user

from app.services import notifications as svc

notifications_bp = Blueprint('notifications', __name__)


ALLOWED_FILTERS = {'all', 'warning', 'danger', 'info', 'success'}


@notifications_bp.route('/')
@login_required
def index():
    all_items = svc.for_user(current_user)
    kind = (request.args.get('kind') or 'all').strip().lower()
    if kind not in ALLOWED_FILTERS:
        kind = 'all'

    if kind == 'all':
        items = all_items
    else:
        items = [n for n in all_items if n['type'] == kind]

    counts = {
        'all': len(all_items),
        'warning': sum(1 for n in all_items if n['type'] == 'warning'),
        'danger': sum(1 for n in all_items if n['type'] == 'danger'),
        'info': sum(1 for n in all_items if n['type'] == 'info'),
        'success': sum(1 for n in all_items if n['type'] == 'success'),
    }

    return render_template(
        'notifications/index.html',
        items=items,
        counts=counts,
        active=kind,
    )


@notifications_bp.route('/count')
@login_required
def count():
    """Lightweight endpoint the client polls after a dismissal."""
    items = svc.for_user(current_user)
    return jsonify({'count': len(items)})


@notifications_bp.route('/<path:key>/dismiss', methods=['POST'])
@login_required
def dismiss(key):
    svc.dismiss(current_user, key)
    wants_json = request.headers.get('X-Requested-With') == 'XMLHttpRequest' \
        or request.is_json \
        or 'application/json' in (request.headers.get('Accept') or '')

    if wants_json:
        remaining = len(svc.for_user(current_user))
        return jsonify({'ok': True, 'count': remaining})

    if request.referrer:
        return redirect(request.referrer)
    return redirect(url_for('notifications.index'))


@notifications_bp.route('/dismiss-all', methods=['POST'])
@login_required
def dismiss_all():
    n = svc.dismiss_all(current_user)
    if n:
        flash(f'Dismissed {n} notification{"s" if n != 1 else ""}.',
              'success')
    else:
        flash('Nothing to dismiss.', 'info')
    return redirect(url_for('notifications.index'))