from datetime import datetime, timedelta
from app.models import MessageLog
from app.services import ratelimit


def test_no_subscription_returns_zero(app, db, associate_org):
    s = ratelimit.check(associate_org)
    assert s.max_minute == 0 and s.max_day == 0
    assert not s.can_send


def test_fresh_org_has_full_budget(app, db, subscribed_associate):
    s = ratelimit.check(subscribed_associate)
    assert s.can_send
    assert s.remaining_minute == s.max_minute
    assert s.remaining_day == s.max_day


def test_recent_sends_reduce_remaining(app, db, subscribed_associate, plan):
    plan.max_per_minute = 5
    plan.max_per_day = 100
    db.session.commit()

    now = datetime.utcnow()
    for i in range(3):
        db.session.add(MessageLog(
            org_id=subscribed_associate.id, phone=f'25670000000{i}',
            body='x', status='sent', sent_at=now - timedelta(seconds=10)))
    db.session.commit()

    s = ratelimit.check(subscribed_associate)
    assert s.remaining_minute == 2
    assert s.remaining_day == 97


def test_old_sends_do_not_count_for_minute(app, db,
                                           subscribed_associate, plan):
    plan.max_per_minute = 5
    db.session.commit()

    db.session.add(MessageLog(
        org_id=subscribed_associate.id, phone='256700000999',
        body='x', status='sent',
        sent_at=datetime.utcnow() - timedelta(minutes=5)))
    db.session.commit()

    s = ratelimit.check(subscribed_associate)
    assert s.remaining_minute == 5


def test_daily_limit_hit(app, db, subscribed_associate, plan):
    plan.max_per_minute = 1000
    plan.max_per_day = 2
    db.session.commit()

    now = datetime.utcnow()
    for i in range(2):
        db.session.add(MessageLog(
            org_id=subscribed_associate.id, phone=f'25670000100{i}',
            body='x', status='sent', sent_at=now - timedelta(hours=1)))
    db.session.commit()

    s = ratelimit.check(subscribed_associate)
    assert s.remaining_day == 0
    assert not s.can_send