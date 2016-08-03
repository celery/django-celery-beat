"""django-celery-beat application configurations."""
from __future__ import absolute_import, unicode_literals

from django.apps import AppConfig
from django.utils.translation import ugettext_lazy as _

__all__ = ['BeatConfig']


class BeatConfig(AppConfig):
    name = 'django_celery_beat'
    label = 'beat'
    verbose_name = _('Beat')
