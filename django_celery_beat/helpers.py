from django.apps import apps
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from .models import (
    PeriodicTask, PeriodicTasks,
    CrontabSchedule, IntervalSchedule,
    SolarSchedule, ClockedSchedule
)

def crontabschedule_model():
    """Return the CrontabSchedule model that is active in this project."""
    if not hasattr(settings, 'CELERY_BEAT_CRONTABSCHEDULE_MODEL'):
        return CrontabSchedule
    
    try:
        return apps.get_model(
            settings.CELERY_BEAT_CRONTABSCHEDULE_MODEL
        )
    except ValueError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_CRONTABSCHEDULE_MODEL must be of the form "
            "'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_CRONTABSCHEDULE_MODEL refers to model "
            f"'{settings.CELERY_BEAT_CRONTABSCHEDULE_MODEL}' that has not "
            "been installed"
        )

def intervalschedule_model():
    """Return the IntervalSchedule model that is active in this project."""
    if not hasattr(settings, 'CELERY_BEAT_INTERVALSCHEDULE_MODEL'):
        return IntervalSchedule
    
    try:
        return apps.get_model(
            settings.CELERY_BEAT_INTERVALSCHEDULE_MODEL
        )
    except ValueError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_INTERVALSCHEDULE_MODEL must be of the form "
            "'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_INTERVALSCHEDULE_MODEL refers to model "
            f"'{settings.CELERY_BEAT_INTERVALSCHEDULE_MODEL}' that has not "
            "been installed"
        )

def periodictask_model():
    """Return the PeriodicTask model that is active in this project."""
    if not hasattr(settings, 'CELERY_BEAT_PERIODICTASK_MODEL'):
        return PeriodicTask
    
    try:
        return apps.get_model(settings.CELERY_BEAT_PERIODICTASK_MODEL)
    except ValueError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_PERIODICTASK_MODEL must be of the form "
            "'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_PERIODICTASK_MODEL refers to model "
            f"'{settings.CELERY_BEAT_PERIODICTASK_MODEL}' that has not been "
            "installed"
        )

def periodictasks_model():
    """Return the PeriodicTasks model that is active in this project."""
    if not hasattr(settings, 'CELERY_BEAT_PERIODICTASKS_MODEL'):
        return PeriodicTasks
    
    try:
        return apps.get_model(
            settings.CELERY_BEAT_PERIODICTASKS_MODEL
        )
    except ValueError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_PERIODICTASKS_MODEL must be of the form "
            "'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_PERIODICTASKS_MODEL refers to model "
            f"'{settings.CELERY_BEAT_PERIODICTASKS_MODEL}' that has not been "
            "installed"
        )

def solarschedule_model():
    """Return the SolarSchedule model that is active in this project."""
    if not hasattr(settings, 'CELERY_BEAT_SOLARSCHEDULE_MODEL'):
        return SolarSchedule
    
    try:
        return apps.get_model(
            settings.CELERY_BEAT_SOLARSCHEDULE_MODEL
        )
    except ValueError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_SOLARSCHEDULE_MODEL must be of the form "
            "'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_SOLARSCHEDULE_MODEL refers to model "
            f"'{settings.CELERY_BEAT_SOLARSCHEDULE_MODEL}' that has not been "
            "installed"
        )

def clockedschedule_model():
    """Return the ClockedSchedule model that is active in this project."""
    if not hasattr(settings, 'CELERY_BEAT_CLOCKEDSCHEDULE_MODEL'):
        return ClockedSchedule
    
    try:
        return apps.get_model(
            settings.CELERY_BEAT_CLOCKEDSCHEDULE_MODEL
        )
    except ValueError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_CLOCKEDSCHEDULE_MODEL must be of the form "
            "'app_label.model_name'"
        )
    except LookupError:
        raise ImproperlyConfigured(
            "CELERY_BEAT_CLOCKEDSCHEDULE_MODEL refers to model "
            f"'{settings.CELERY_BEAT_CLOCKEDSCHEDULE_MODEL}' that has not "
            "been installed"
        )
