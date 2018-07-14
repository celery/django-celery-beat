import contextlib
import io
import sys

from crontab import CronTab
from django.core.exceptions import ValidationError


@contextlib.contextmanager
def redirect_stderr(target):
    original = sys.stderr
    sys.stderr = target
    yield
    sys.stderr = original


def validate_crontab(value, index):
    """
    Validate single part of cron tab.
    :param value:
    :param index: position in crontab
    :return:
    """
    tab = ['*'] * 5
    tab.append('dummy_command')  # force crontab parsing
    tab[index] = value
    tab = ' '.join(tab)
    f = io.StringIO()
    with redirect_stderr(f):
        CronTab(tab=tab)
    err = f.getvalue()
    if err:
        raise ValidationError(err)


def minute_validator(value):
    validate_crontab(value, 0)


def hour_validator(value):
    validate_crontab(value, 1)


def day_of_month_validator(value):
    validate_crontab(value, 2)


def month_of_year_validator(value):
    validate_crontab(value, 3)


def day_of_week_validator(value):
    validate_crontab(value, 4)
