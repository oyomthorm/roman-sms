from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, abort)
from flask_login import current_user

from app.extensions import limiter
from app.services import signups as svc
from app.services import plans as plans_svc
from app.services import geo as geo_svc

signup_bp = Blueprint('signup', __name__)


def _signup_enabled():
    return current_app.config.get('SIGNUP_ENABLED', True)


@signup_bp.route('/', methods=['GET'])
@limiter.limit('30 per hour')
def form():
    if not _signup_enabled():
        abort(404)
    if current_user.is_authenticated:
        return redirect(url_for('landing.index'))
    return render_template(
        'signup/form.html',
        plans=plans_svc.list_for_pricing(),
        districts_by_region=geo_svc.list_by_region(),
        form={},
    )


@signup_bp.route('/', methods=['POST'])
@limiter.limit('10 per hour')
def submit():
    if not _signup_enabled():
        abort(404)

    # Honeypot. A real user never fills this.
    if request.form.get('website'):
        # Silently accept and drop.
        return redirect(url_for('signup.pending'))

    try:
        req, created = svc.submit_request(
            company_name=request.form.get('company_name', ''),
            desired_slug=request.form.get('desired_slug', ''),
            brand_name=request.form.get('brand_name', ''),
            contact_name=request.form.get('contact_name', ''),
            contact_email=request.form.get('contact_email', ''),
            contact_phone=request.form.get('contact_phone', ''),
            district_id=request.form.get('district_id', type=int),
            plan_id=request.form.get('plan_id', type=int),
            expected_volume=request.form.get('expected_volume', ''),
            message=request.form.get('message', ''),
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')[:255],
        )
    except svc.SignupError as e:
        flash(str(e), 'danger')
        return render_template(
            'signup/form.html',
            plans=plans_svc.list_for_pricing(),
            districts_by_region=geo_svc.list_by_region(),
            form=request.form,
        )

    # Stash the email for the pending page so we can reference it.
    flash(
        f'Thank you. If your application is approved, we will email '
        f'{req.contact_email} with a link to set your password.',
        'success',
    )
    return redirect(url_for('signup.pending'))


@signup_bp.route('/pending')
def pending():
    if not _signup_enabled():
        abort(404)
    return render_template('signup/pending.html')