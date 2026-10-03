from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app)
from flask_login import current_user

from app.extensions import db, limiter
from app.models import OptOut, User
from app.services import optout_links
from app.services import mailer, password_reset
from app.services.phones import normalize_ug
from app.services.audit import log as audit

public_bp = Blueprint('public', __name__)


# --------------------------------------------------------------------------
# Opt-out
# --------------------------------------------------------------------------

@public_bp.route('/opt-out')
def optout_landing():
    """Manual entry — the visitor types their phone number."""
    return render_template('public/optout.html', phone=None)


@public_bp.route('/opt-out', methods=['POST'])
@limiter.limit('10 per minute')
def optout_submit():
    from app.services import pool as pool_svc

    raw = request.form.get('phone', '')
    phone = normalize_ug(raw)
    if not phone:
        flash('That does not look like a Ugandan phone number.', 'danger')
        return render_template('public/optout.html', phone=raw), 400

    if not OptOut.query.filter_by(phone=phone).first():
        db.session.add(OptOut(phone=phone, reason='public_landing'))
        db.session.flush()
        pool_svc.propagate_opt_out(phone)
        db.session.commit()
        audit('optout_public', phone, actor_id=None)

    return render_template('public/optout_done.html', phone=phone)


@public_bp.route('/opt-out/<token>')
@limiter.limit('30 per minute')
def optout_token(token):
    phone = optout_links.read_token(token)
    if not phone:
        return render_template('public/optout.html', phone=None,
                               error='That link has expired or is invalid.'), 400
    return render_template('public/optout.html', phone=phone, token=token)


@public_bp.route('/opt-out/<token>', methods=['POST'])
@limiter.limit('30 per minute')
def optout_token_confirm(token):
    from app.services import pool as pool_svc

    phone = optout_links.read_token(token)
    if not phone:
        return render_template('public/optout.html', phone=None,
                               error='That link has expired or is invalid.'), 400

    if not OptOut.query.filter_by(phone=phone).first():
        db.session.add(OptOut(phone=phone, reason='public_link'))
        db.session.flush()
        pool_svc.propagate_opt_out(phone)
        db.session.commit()
        audit('optout_link', phone, actor_id=None)

    return render_template('public/optout_done.html', phone=phone)


# --------------------------------------------------------------------------
# Password reset
# --------------------------------------------------------------------------

@public_bp.route('/forgot-password', methods=['GET', 'POST'])
@limiter.limit('5 per minute')
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user = User.query.filter_by(email=email, is_active_flag=True).first()
        if user:
            token = password_reset.make_token(user)
            base = current_app.config.get('PUBLIC_BASE_URL', '')
            url = f'{base.rstrip("/")}/reset-password/{token}' if base else token
            mailer.send(
                to=user.email,
                subject='Reset your Roman SMS password',
                body_text=(
                    f'Hello,\n\n'
                    f'Use this link to reset your password:\n{url}\n\n'
                    f'The link expires in 1 hour.\n\n'
                    f'If you did not request this, you can ignore this email.'
                ),
            )
        # Always show the same message — do not confirm whether the email exists.
        flash('If that email is registered, a reset link has been sent.',
              'info')
        return redirect(url_for('public.forgot_password'))
    return render_template('public/forgot_password.html')


@public_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@limiter.limit('10 per minute')
def reset_password(token):
    candidates = User.query.filter_by(is_active_flag=True).all()
    user = next(
        (u for u in candidates
         if password_reset.read_token(u, token, purpose='reset')
         or password_reset.read_token(u, token, purpose='welcome')),
        None,
    )
    if not user:
        return render_template('public/reset_password.html',
                               token=token,
                               error='Link is invalid or expired.'), 400

    if request.method == 'POST':
        new_password = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if len(new_password) < 8:
            flash('Password must be at least 8 characters.', 'danger')
        elif new_password != confirm:
            flash('Passwords do not match.', 'danger')
        else:
            user.set_password(new_password)
            db.session.commit()
            audit('password_reset', user.email,
                  org_id=user.org_id, actor_id=user.id)
            flash('Password updated. You can log in now.', 'success')
            return redirect(url_for('auth.login'))

    return render_template('public/reset_password.html',
                           token=token, error=None)