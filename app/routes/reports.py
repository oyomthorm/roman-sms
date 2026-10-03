import csv
import io
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, Response
from flask_login import login_required, current_user

from app.models import MessageLog

reports_bp = Blueprint('reports', __name__)


def _org():
    return current_user.organization


@reports_bp.route('/log')
@login_required
def log():
    status = request.args.get('status', '')
    days = int(request.args.get('days', 7))
    since = datetime.utcnow() - timedelta(days=days)

    q = MessageLog.query.filter_by(org_id=_org().id)
    q = q.filter(MessageLog.created_at >= since)
    if status:
        q = q.filter_by(status=status)
    rows = q.order_by(MessageLog.id.desc()).limit(1000).all()
    return render_template('reports/log.html',
                           rows=rows, status=status, days=days)


@reports_bp.route('/log.csv')
@login_required
def log_csv():
    days = int(request.args.get('days', 7))
    since = datetime.utcnow() - timedelta(days=days)
    rows = (MessageLog.query
            .filter_by(org_id=_org().id)
            .filter(MessageLog.created_at >= since)
            .order_by(MessageLog.id.desc()).limit(50000).all())
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['id', 'campaign_id', 'phone', 'status', 'sent_at', 'body'])
    for r in rows:
        w.writerow([r.id, r.campaign_id, r.phone, r.status,
                    r.sent_at.isoformat() if r.sent_at else '',
                    (r.body or '')[:200]])
    return Response(buf.getvalue(), mimetype='text/csv',
                    headers={'Content-Disposition':
                             'attachment; filename=messages.csv'})