from flask import Blueprint, render_template, redirect, url_for
from flask_login import current_user

from app.services import plans as plans_svc


landing_bp = Blueprint('landing', __name__)


@landing_bp.route('/')
def index():
    # Logged-in users go straight to their dashboard.
    if current_user.is_authenticated:
        if current_user.is_master:
            return redirect(url_for('master.index'))
        return redirect(url_for('dashboard.index'))

    plans = plans_svc.list_for_pricing()
    return render_template('landing/index.html', plans=plans)