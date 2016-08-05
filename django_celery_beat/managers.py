from __future__ import absolute_import, unicode_literals

from celery.five import items

from django.db import models
from django.db.models.query import QuerySet


class ExtendedQuerySet(QuerySet):

    def update_or_create(self, defaults=None, **kwargs):
        obj, created = self.get_or_create(defaults=defaults, **kwargs)
        if not created:
            self._update_model_with_dict(obj, dict(defaults or {}, **kwargs))
        return obj

    def _update_model_with_dict(self, obj, fields):
        [setattr(obj, attr_name, attr_value)
            for attr_name, attr_value in items(fields)]
        obj.save()
        return obj


class ExtendedManager(models.Manager.from_queryset(ExtendedQuerySet)):
    pass


class PeriodicTaskManager(ExtendedManager):

    def enabled(self):
        return self.filter(enabled=True)
