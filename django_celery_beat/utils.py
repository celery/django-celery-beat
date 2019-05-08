"""Utilities."""
# -- XXX This module must not use translation as that causes
# -- a recursive loader import!
from __future__ import absolute_import, unicode_literals

from django.conf import settings
from django.utils import timezone

from celery import current_app

is_aware = timezone.is_aware


def make_aware(value):
    """Force datatime to have timezone information."""
    if getattr(settings, 'CELERY_TIMEZONE', False):
        # naive datetimes are assumed to be in UTC.
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.utc)
        # then convert to the Django configured timezone.
        value = value.astimezone(current_app.tz)
    else:
        # naive datetimes are assumed to be in local timezone.
        if timezone.is_naive(value):
            value = timezone.make_aware(value, timezone.get_default_timezone())
    return value


def now():
    """Return the current date and time."""
    if getattr(settings, 'CELERY_TIMEZONE', False):
        return timezone.now().astimezone(current_app.tz)
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
