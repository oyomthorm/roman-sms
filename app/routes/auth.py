from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models import User
from app.services.audit import log as audit
from app.extensions import limiter

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('landing.index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        pw = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()

        # Generic message: never confirm whether the account exists.
        if not user or not user.check_password(pw) or not user.is_active_flag:
            flash('Invalid email or password.', 'danger')
            return render_template('auth/login.html')

        if user.organization.status != 'active' and not user.is_master:
            flash('Your organization is suspended. Contact support.', 'danger')
            return render_template('auth/login.html')

        login_user(user)
        user.last_login = datetime.utcnow()
        db.session.commit()
        audit('login')

        if user.is_master:
            return redirect(url_for('master.index'))
        return redirect(url_for('dashboard.index'))

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))