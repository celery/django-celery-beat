"""Utilities."""
import datetime
# -- XXX This module must not use translation as that causes
# -- a recursive loader import!
from datetime import timezone as datetime_timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python 3.8

from celery import current_app
from django.conf import settings
from django.utils import timezone

is_aware = timezone.is_aware
# celery schedstate return None will make it not work
NEVER_CHECK_TIMEOUT = 100000000
# This scheduler must wake up more frequently than the
# regular interval of 5 minutes because it needs to take
# external changes to the schedule into account.
DEFAULT_MAX_INTERVAL = 5  # seconds
SCHEDULE_SYNC_MAX_INTERVAL = 300  # 5 minutes

# see Issue #222
now_localtime = getattr(timezone, 'template_localtime', timezone.localtime)


def make_aware(value):
    """Force datatime to have timezone information."""
    if getattr(settings, 'USE_TZ', False):
        # naive datetimes are assumed to be in UTC.
        if timezone.is_naive(value):
            value = timezone.make_aware(value, datetime_timezone.utc)
        # then convert to the Django configured timezone.
        default_tz = timezone.get_default_timezone()
        value = timezone.localtime(value, default_tz)
    elif timezone.is_naive(value):
        # naive datetimes are assumed to be in local timezone.
        value = timezone.make_aware(value, timezone.get_default_timezone())
    return value


def now():
    """Return the current date and time."""
    if getattr(settings, 'USE_TZ', False):
        return now_localtime(timezone.now())
    else:
        return timezone.now()


def aware_now():
    if getattr(settings, 'USE_TZ', True):
        # When USE_TZ is True, return timezone.now()
        return timezone.now()
    else:
        # When USE_TZ is False, use the project's timezone
        project_tz = ZoneInfo(getattr(settings, 'TIME_ZONE', 'UTC'))
        return datetime.datetime.now(project_tz)


def is_database_scheduler(scheduler):
    """Return true if Celery is configured to use the db scheduler."""
    if not scheduler:
        return False
    from kombu.utils import symbol_by_name  # noqa: PLC0415

    from .schedulers import DatabaseScheduler  # noqa: PLC0415
    return (
        scheduler == 'django'
        or issubclass(symbol_by_name(scheduler), DatabaseScheduler)
    )


def next_schedule_sync_at(now_func=now):
    """Scheduled time of the next full schedule sync."""
    return now_func() + datetime.timedelta(seconds=SCHEDULE_SYNC_MAX_INTERVAL)


def next_schedule_sync_by(now_func=now):
    """Latest time by which the next full schedule sync must have run."""
    max_interval = (
        current_app.conf.beat_max_loop_interval or DEFAULT_MAX_INTERVAL)
    return next_schedule_sync_at(now_func) + datetime.timedelta(seconds=max_interval)


def clocked_due_after_next_sync(clocked_time):
    """True if the clocked task is due after the next full schedule sync."""
    use_tz = getattr(settings, 'USE_TZ', False)
    clocked_aware = timezone.is_aware(clocked_time)
    now_func = now
    # keep clocked_time and the deadline both aware or both naive
    if clocked_aware and not use_tz:
        now_func = aware_now
    elif use_tz and not clocked_aware:
        clocked_time = timezone.make_aware(
            clocked_time, timezone.get_default_timezone()
        )
    return clocked_time > next_schedule_sync_by(now_func)
