"""Utilities."""
import os

import Crypto.PublicKey.RSA as RSA
# -- XXX This module must not use translation as that causes
# -- a recursive loader import!
from django.conf import settings
from django.utils import timezone

is_aware = timezone.is_aware
# celery schedstate return None will make it not work
NEVER_CHECK_TIMEOUT = 100000000

# see Issue #222
now_localtime = getattr(timezone, 'template_localtime', timezone.localtime)


def _load_keys():
    private_key_path = os.environ.get('DJANGO_CELERY_BEAT_PRIVATE_KEY_PATH', './id_rsa')
    public_key_path = os.environ.get('DJANGO_CELERY_BEAT_PUBLIC_KEY_PATH', './id_rsa.pub')

    if os.path.exists(private_key_path):
        with open(private_key_path, 'r') as id_rsa:
            private_key = RSA.importKey(id_rsa.read())
            public_key = private_key.publickey()
    else:
        private_key = RSA.generate(4096, os.urandom)
        public_key = private_key.publickey()

        os.chmod(private_key_path, 0o600)
        with open(private_key_path, 'wb+') as id_rsa:
            id_rsa.write(private_key.exportKey())

        with open(public_key_path, 'wb') as id_rsa_pub:
            id_rsa_pub.write(public_key.exportKey())

    return private_key, public_key


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
            value = timezone.make_aware(value, timezone.get_default_timezone())
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


def sign(data):
    """Sign the data to protect against database changes and return signature in hex"""
    return hex(_private_key.sign(data, '')[0])


def verify(data, signature):
    """Check the signature and return True if it is correct for the specified data"""
    return _public_key.verify(data, signature)


_private_key, _public_key = _load_keys()
