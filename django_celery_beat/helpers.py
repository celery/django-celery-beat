"""Helpers for resolving active django-celery-beat model classes."""

from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import (ClockedSchedule, CrontabSchedule, IntervalSchedule,
                     PeriodicTask, PeriodicTasks, SolarSchedule)


def _configured_model(setting_name, default_model):
    """Return the model configured by setting_name or default_model."""
    model_label = getattr(settings, setting_name, None)
    if model_label is None:
        return default_model

    try:
        return apps.get_model(model_label)
    except ValueError as exc:
        raise ImproperlyConfigured(
            f"{setting_name} must be of the form app_label.ModelName; "
            f"got {model_label!r}"
        ) from exc
    except LookupError as exc:
        raise ImproperlyConfigured(
            f"{setting_name} refers to model {model_label!r} that has not "
            "been installed"
        ) from exc


def crontabschedule_model():
    """Return the CrontabSchedule model active in this project."""
    return _configured_model(
        "CELERY_BEAT_CRONTABSCHEDULE_MODEL", CrontabSchedule
    )


def intervalschedule_model():
    """Return the IntervalSchedule model active in this project."""
    return _configured_model(
        "CELERY_BEAT_INTERVALSCHEDULE_MODEL", IntervalSchedule
    )


def periodictask_model():
    """Return the PeriodicTask model active in this project."""
    return _configured_model(
        "CELERY_BEAT_PERIODICTASK_MODEL", PeriodicTask
    )


def periodictasks_model():
    """Return the PeriodicTasks model active in this project."""
    return _configured_model(
        "CELERY_BEAT_PERIODICTASKS_MODEL", PeriodicTasks
    )


def solarschedule_model():
    """Return the SolarSchedule model active in this project."""
    return _configured_model(
        "CELERY_BEAT_SOLARSCHEDULE_MODEL", SolarSchedule
    )


def clockedschedule_model():
    """Return the ClockedSchedule model active in this project."""
    return _configured_model(
        "CELERY_BEAT_CLOCKEDSCHEDULE_MODEL", ClockedSchedule
    )
