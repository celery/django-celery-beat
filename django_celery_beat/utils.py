"""Utilities."""
import os
from hashlib import sha256

import Crypto.PublicKey.RSA as RSA
# -- XXX This module must not use translation as that causes
# -- a recursive loader import!
from celery.utils.log import get_logger
from django.conf import settings
from django.utils import timezone
from functools import lru_cache

is_aware = timezone.is_aware
# celery schedstate return None will make it not work
NEVER_CHECK_TIMEOUT = 100000000

# see Issue #222
now_localtime = getattr(timezone, 'template_localtime', timezone.localtime)

logger = get_logger(__name__)


def generate_keys(
    private_key_path=os.environ.get('DJANGO_CELERY_BEAT_PRIVATE_KEY_PATH', './id_rsa'),
    public_key_path=os.environ.get('DJANGO_CELERY_BEAT_PUBLIC_KEY_PATH', './id_rsa.pub')
):
    private_key = RSA.generate(4096, os.urandom)
    public_key = private_key.publickey()

    if os.path.exists(private_key_path):
        if input('Do you realy want to rewrite `{}` key file? [y/n]: '.format(private_key_path)) != 'y':
            return

    if os.path.exists(public_key_path):
        if input('Do you realy want to rewrite `{}` key file? [y/n]: '.format(public_key_path)) != 'y':
            return

    open(private_key_path, 'wb').close()
    os.chmod(private_key_path, 0o600)
    with open(private_key_path, 'wb') as id_rsa:
        id_rsa.write(private_key.exportKey())

    open(public_key_path, 'wb').close()
    os.chmod(public_key_path, 0o644)
    with open(public_key_path, 'wb') as id_rsa_pub:
        id_rsa_pub.write(public_key.exportKey())


@lru_cache(maxsize=None)
def _load_private_key():
    private_key_path = os.environ.get('DJANGO_CELERY_BEAT_PRIVATE_KEY_PATH', './id_rsa')

    if os.path.exists(private_key_path):
        with open(private_key_path, 'rb') as id_rsa:
            private_key = RSA.importKey(id_rsa.read())
        return private_key

    raise FileNotFoundError(
        'Private key not found. Use `django_celery_beat.utils.generate_keys` '
        'to generate new RSA keys... [{}]'.format(private_key_path)
    )


@lru_cache(maxsize=None)
def _load_public_key():
    public_key_path = os.environ.get('DJANGO_CELERY_BEAT_PUBLIC_KEY_PATH', './id_rsa.pub')

    if os.path.exists(public_key_path):
        with open(public_key_path, 'rb') as id_rsa_pub:
            _public_key = RSA.importKey(id_rsa_pub.read())
        return _public_key

    raise FileNotFoundError(
        'Private key not found. Use `django_celery_beat.utils.generate_keys` '
        'to generate new RSA keys... [{}]'.format(public_key_path)
    )


def _load_keys():
    return _load_private_key(), _load_public_key()


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


def sign_task_signature(serialized_task_signature):
    """Sign the bytes data to protect against database changes and return signature in hex"""
    private_key = _load_private_key()

    assert isinstance(serialized_task_signature, bytes), ValueError('Data must be bytes')
    return hex(private_key.sign(sha256(serialized_task_signature).hexdigest().encode(), '')[0])


def verify_task_signature(serialized_task_signature, sign_in_hex):
    """Check the signature and return True if it is correct for the specified data"""
    public_key = _load_public_key()

    return public_key.verify(sha256(serialized_task_signature).hexdigest().encode(), (int(sign_in_hex, 16),))
