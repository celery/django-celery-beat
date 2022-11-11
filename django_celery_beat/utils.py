"""Utilities."""
# -- XXX This module must not use translation as that causes
# -- a recursive loader import!
from django.conf import settings
from django.utils import timezone
import time

is_aware = timezone.is_aware
# celery schedstate return None will make it not work
NEVER_CHECK_TIMEOUT = 100000000

# see Issue #222
now_localtime = getattr(timezone, 'template_localtime', timezone.localtime)


def make_aware(value):
    """Force datatime to have timezone information."""
    if getattr(settings, 'USE_TZ', False):
        # naive datetimes are assumed to be in UTC.
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.utc)
        # then convert to the Django configured timezone.
        default_tz = timezone.get_default_timezone()
        value = timezone.localtime(value, default_tz)
    else:
        # naive datetimes are assumed to be in local timezone.
        if timezone.is_naive(value):
            tm_isdst = time.localtime().tm_isdst

            # tm_isdst may return -1 if it cannot be determined
            if tm_isdst == -1:
                is_dst = None
            else:
                is_dst = bool(tm_isdst)

            value = timezone.make_aware(value, timezone.get_default_timezone(), is_dst=is_dst)
    return value


def now():
    """Return the current date and time."""
    if getattr(settings, 'USE_TZ', False):
        return now_localtime(timezone.now())
    else:
        return timezone.now()


def is_database_scheduler(scheduler):
    """Return true if Celery is configured to use the db scheduler."""
    if not scheduler:
        return False
    from kombu.utils import symbol_by_name

    from .schedulers import DatabaseScheduler
    return (
        scheduler == 'django'
        or issubclass(symbol_by_name(scheduler), DatabaseScheduler)
    )
