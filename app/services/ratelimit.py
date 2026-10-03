"""
Per-org rate limiting. Plan caps are already stored on Plan.max_per_minute
and Plan.max_per_day. This module counts recent sends from MessageLog and
tells the dispatcher how much headroom an org has.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.models import MessageLog
from app.services.entitlements import active_subscription


@dataclass
class LimitStatus:
    remaining_minute: int
    remaining_day: int
    max_minute: int
    max_day: int

    @property
    def can_send(self):
        return self.remaining_minute > 0 and self.remaining_day > 0


def _count_since(org_id, since):
    return (MessageLog.query
            .filter(MessageLog.org_id == org_id,
                    MessageLog.status == 'sent',
                    MessageLog.sent_at >= since)
            .count())


def check(org):
    """
    Return a LimitStatus for org as of now.
    An org with no active plan gets zeros — cannot send.
    """
    sub = active_subscription(org.id)
    if not sub or not sub.plan:
        return LimitStatus(0, 0, 0, 0)

    max_minute = sub.plan.max_per_minute or 60
    max_day = sub.plan.max_per_day or 5000

    now = datetime.utcnow()
    used_minute = _count_since(org.id, now - timedelta(seconds=60))
    used_day = _count_since(org.id, now - timedelta(hours=24))

    return LimitStatus(
        remaining_minute=max(0, max_minute - used_minute),
        remaining_day=max(0, max_day - used_day),
        max_minute=max_minute,
        max_day=max_day,
    )