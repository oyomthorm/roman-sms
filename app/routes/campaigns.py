from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash)
from flask_login import login_required, current_user

from app.models import Campaign, MessageLog
from app.permissions import org_scoped
from app.services import campaigns as svc
from app.services import templates_svc
from app.services import groups as groups_svc
from app.services import geo as geo_svc
from app.services.wallet import get_balance
from app.services.phones import parse_pasted_numbers
from app.models import CampaignSchedule
from app.services import schedules as schedules_svc

campaigns_bp = Blueprint('campaigns', __name__)


def _org():
    return current_user.organization


@campaigns_bp.route('/')
@login_required
def index():
    campaigns = (org_scoped(Campaign)
                 .order_by(Campaign.id.desc()).limit(100).all())
    return render_template('campaigns/list.html', campaigns=campaigns)


@campaigns_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    org = _org()
    templates = templates_svc.list_templates(org)
    groups = groups_svc.list_groups(org)
    districts_by_region = geo_svc.list_by_region()

    if request.method == 'POST':
        mode = request.form.get('mode', 'now')   # 'now' or 'schedule'
        recipient_source = (request.form.get('recipient_source')
                            or 'group').strip()

        template_id = request.form.get('template_id') or None

        group_id = None
        group_name = None
        district_id = None
        district_name = None
        custom_phones = None

        if recipient_source == 'paste':
            if mode == 'schedule':
                flash('Scheduled campaigns send to your contact list. '
                      'To use a pasted list, choose "Send now".', 'danger')
                return render_template(
                    'campaigns/new.html',
                    templates=templates, groups=groups,
                    districts_by_region=districts_by_region,
                    balance=get_balance(org.id))

            custom_phones = parse_pasted_numbers(
                request.form.get('pasted_numbers', ''),
                max_count=500,
            )
            if not custom_phones:
                flash('No valid phone numbers found in the pasted list. '
                      'Numbers must be Ugandan mobiles.', 'danger')
                return render_template(
                    'campaigns/new.html',
                    templates=templates, groups=groups,
                    districts_by_region=districts_by_region,
                    balance=get_balance(org.id))
        else:
            group_id_raw = request.form.get('group_id', '').strip()
            group_id = int(group_id_raw) if group_id_raw.isdigit() else None
            district_id_raw = request.form.get('district_id', '').strip()
            district_id = (int(district_id_raw)
                           if district_id_raw.isdigit() else None)

            if group_id:
                g = groups_svc.get(org, group_id)
                if g:
                    group_name = g.name

            if district_id:
                d = geo_svc.get(district_id)
                if d:
                    district_name = d.name

        if mode == 'schedule':
            scheduled_times = request.form.getlist('scheduled_times')
            try:
                schedule = schedules_svc.create_schedule(
                    org,
                    name=request.form.get('name', ''),
                    body=request.form.get('body', ''),
                    times=scheduled_times,
                    group_id=group_id,
                    district_id=district_id,
                    template_id=int(template_id) if template_id else None,
                    created_by=current_user.id,
                )
            except schedules_svc.ScheduleError as e:
                flash(str(e), 'danger')
                return render_template(
                    'campaigns/new.html',
                    templates=templates, groups=groups,
                    districts_by_region=districts_by_region,
                    balance=get_balance(org.id))

            n = schedule.run_count
            flash(f'Schedule created with {n} send'
                  f'{"s" if n != 1 else ""}. First run: '
                  f'{schedule.next_run_at.strftime("%d %b, %H:%M")} UTC.',
                  'success')
            return redirect(url_for('campaigns.schedule_detail',
                                    sid=schedule.id))

        # Send now (default path)
        try:
            campaign, segs = svc.create_campaign(
                org,
                name=request.form.get('name', ''),
                body=request.form.get('body', ''),
                group_id=group_id, group_name=group_name,
                district_id=district_id, district_name=district_name,
                custom_phones=custom_phones,
                template_id=int(template_id) if template_id else None,
                created_by=current_user.id,
            )
        except svc.CampaignError as e:
            flash(str(e), 'danger')
            return render_template('campaigns/new.html',
                                   templates=templates, groups=groups,
                                   districts_by_region=districts_by_region,
                                   balance=get_balance(org.id))
        flash(f'Campaign queued: {campaign.total} recipients, '
              f'{segs} SMS.', 'success')
        return redirect(url_for('campaigns.detail', cid=campaign.id))

    return render_template('campaigns/new.html',
                           templates=templates, groups=groups,
                           districts_by_region=districts_by_region,
                           balance=get_balance(org.id))


@campaigns_bp.route('/<int:cid>')
@login_required
def detail(cid):
    campaign = org_scoped(Campaign).filter_by(id=cid).first_or_404()
    logs = (MessageLog.query.filter_by(campaign_id=campaign.id)
            .order_by(MessageLog.id.desc()).limit(200).all())
    breakdown = svc.delivery_breakdown(campaign.id)
    return render_template('campaigns/detail.html',
                           campaign=campaign, logs=logs,
                           breakdown=breakdown)


@campaigns_bp.route('/<int:cid>/cancel', methods=['POST'])
@login_required
def cancel(cid):
    campaign = org_scoped(Campaign).filter_by(id=cid).first_or_404()
    if svc.cancel_campaign(campaign, actor_id=current_user.id):
        flash('Campaign cancelled.', 'success')
    else:
        flash('Campaign already finished.', 'warning')
    return redirect(url_for('campaigns.detail', cid=campaign.id))


# --------------------------------------------------------------------------
# Schedules
# --------------------------------------------------------------------------

@campaigns_bp.route('/schedules')
@login_required
def schedules():
    org = _org()
    rows = (CampaignSchedule.query
            .filter_by(org_id=org.id)
            .order_by(CampaignSchedule.id.desc())
            .limit(100).all())
    return render_template('campaigns/schedules.html', schedules=rows)


@campaigns_bp.route('/schedules/<int:sid>')
@login_required
def schedule_detail(sid):
    org = _org()
    schedule = CampaignSchedule.query.filter_by(
        id=sid, org_id=org.id).first_or_404()
    runs = schedule.runs.limit(50).all()
    return render_template('campaigns/schedule_detail.html',
                           schedule=schedule, runs=runs)


@campaigns_bp.route('/schedules/<int:sid>/pause', methods=['POST'])
@login_required
def schedule_pause(sid):
    schedule = CampaignSchedule.query.filter_by(
        id=sid, org_id=_org().id).first_or_404()
    schedules_svc.pause_schedule(schedule, actor_id=current_user.id)
    flash('Schedule paused.', 'success')
    return redirect(url_for('campaigns.schedule_detail', sid=sid))


@campaigns_bp.route('/schedules/<int:sid>/resume', methods=['POST'])
@login_required
def schedule_resume(sid):
    schedule = CampaignSchedule.query.filter_by(
        id=sid, org_id=_org().id).first_or_404()
    schedules_svc.resume_schedule(schedule, actor_id=current_user.id)
    flash('Schedule resumed.', 'success')
    return redirect(url_for('campaigns.schedule_detail', sid=sid))


@campaigns_bp.route('/schedules/<int:sid>/cancel', methods=['POST'])
@login_required
def schedule_cancel(sid):
    schedule = CampaignSchedule.query.filter_by(
        id=sid, org_id=_org().id).first_or_404()
    schedules_svc.cancel_schedule(schedule, actor_id=current_user.id)
    flash('Schedule cancelled.', 'success')
    return redirect(url_for('campaigns.schedules'))