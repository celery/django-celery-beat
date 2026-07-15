from unittest.mock import Mock

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db.models import signals
from django.test import override_settings

from django_celery_beat import helpers
from django_celery_beat.models import PeriodicTask, PeriodicTasks
from django_celery_beat.signals import signals_connect
from t.proj.models import O2OToPeriodicTasks


def test_periodictask_model_returns_default_model():
    assert helpers.periodictask_model() is PeriodicTask


@override_settings(CELERY_BEAT_PERIODICTASK_MODEL="proj.O2OToPeriodicTasks")
def test_periodictask_model_returns_configured_model():
    assert helpers.periodictask_model() is O2OToPeriodicTasks


@override_settings(CELERY_BEAT_PERIODICTASK_MODEL="invalid-label")
def test_configured_model_rejects_invalid_model_label():
    with pytest.raises(ImproperlyConfigured):
        helpers.periodictask_model()


@override_settings(CELERY_BEAT_PERIODICTASK_MODEL="proj.MissingModel")
def test_configured_model_rejects_missing_model():
    with pytest.raises(ImproperlyConfigured):
        helpers.periodictask_model()


@override_settings(CELERY_BEAT_PERIODICTASKS_MODEL="invalid-label")
def test_abstract_periodic_task_rejects_invalid_periodic_tasks_model_label():
    with pytest.raises(ImproperlyConfigured):
        PeriodicTask._periodic_tasks_model()


@override_settings(CELERY_BEAT_PERIODICTASKS_MODEL="proj.MissingModel")
def test_abstract_periodic_task_rejects_missing_periodic_tasks_model():
    with pytest.raises(ImproperlyConfigured):
        PeriodicTask._periodic_tasks_model()


@override_settings(CELERY_BEAT_PERIODICTASKS_MODEL=None)
def test_abstract_periodic_task_uses_default_periodic_tasks_model_for_none_setting():
    assert PeriodicTask._periodic_tasks_model() is PeriodicTasks


def test_signals_connect_uses_active_model_resolvers(monkeypatch):
    class ActiveClockedSchedule:
        pass

    class ActiveCrontabSchedule:
        pass

    class ActiveIntervalSchedule:
        pass

    class ActivePeriodicTask:
        pass

    class ActiveSolarSchedule:
        pass

    class ActivePeriodicTasks:
        changed = Mock()
        update_changed = Mock()

    monkeypatch.setattr(
        helpers, "clockedschedule_model", lambda: ActiveClockedSchedule
    )
    monkeypatch.setattr(
        helpers, "crontabschedule_model", lambda: ActiveCrontabSchedule
    )
    monkeypatch.setattr(
        helpers, "intervalschedule_model", lambda: ActiveIntervalSchedule
    )
    monkeypatch.setattr(
        helpers, "periodictask_model", lambda: ActivePeriodicTask
    )
    monkeypatch.setattr(
        helpers, "periodictasks_model", lambda: ActivePeriodicTasks
    )
    monkeypatch.setattr(
        helpers, "solarschedule_model", lambda: ActiveSolarSchedule
    )

    pre_save_connect = Mock()
    pre_delete_connect = Mock()
    post_save_connect = Mock()
    post_delete_connect = Mock()
    monkeypatch.setattr(signals.pre_save, "connect", pre_save_connect)
    monkeypatch.setattr(signals.pre_delete, "connect", pre_delete_connect)
    monkeypatch.setattr(signals.post_save, "connect", post_save_connect)
    monkeypatch.setattr(signals.post_delete, "connect", post_delete_connect)

    signals_connect()

    pre_save_connect.assert_called_once_with(
        ActivePeriodicTasks.changed, sender=ActivePeriodicTask
    )
    assert pre_delete_connect.call_args_list == [
        ((ActivePeriodicTasks.changed,), {"sender": ActivePeriodicTask}),
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveIntervalSchedule}),
    ]
    assert post_save_connect.call_args_list == [
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveIntervalSchedule}),
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveCrontabSchedule}),
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveSolarSchedule}),
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveClockedSchedule}),
    ]
    assert post_delete_connect.call_args_list == [
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveCrontabSchedule}),
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveSolarSchedule}),
        ((ActivePeriodicTasks.update_changed,), {"sender": ActiveClockedSchedule}),
    ]
