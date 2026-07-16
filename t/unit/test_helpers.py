from unittest.mock import Mock

import pytest
from celery import schedules
from django.core.exceptions import ImproperlyConfigured
from django.db.models import signals
from django.test import override_settings

from django_celery_beat import helpers, schedulers
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
    with pytest.raises(ImproperlyConfigured) as exc_info:
        helpers.periodictask_model()

    assert "CELERY_BEAT_PERIODICTASK_MODEL" in str(exc_info.value)
    assert "app_label.ModelName" in str(exc_info.value)
    assert "invalid-label" in str(exc_info.value)


@override_settings(CELERY_BEAT_PERIODICTASK_MODEL="proj.MissingModel")
def test_configured_model_rejects_missing_model():
    with pytest.raises(ImproperlyConfigured) as exc_info:
        helpers.periodictask_model()

    assert "proj.MissingModel" in str(exc_info.value)


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


def test_scheduler_model_entry_resolves_periodic_task_lazily(monkeypatch):
    class ActivePeriodicTask:
        _default_manager = Mock()

    model = Mock()
    ActivePeriodicTask._default_manager.update_or_create.return_value = (
        model, True,
    )
    monkeypatch.setattr(
        helpers, "periodictask_model", lambda: ActivePeriodicTask
    )
    init = Mock(return_value=None)
    monkeypatch.setattr(
        schedulers.ModelEntry, "_unpack_fields", Mock(return_value={})
    )
    monkeypatch.setattr(schedulers.ModelEntry, "__init__", init)

    entry = schedulers.ModelEntry.from_entry("lazy-task")

    ActivePeriodicTask._default_manager.update_or_create.assert_called_once_with(
        name="lazy-task", defaults={}
    )
    init.assert_called_once_with(model, app=None)
    assert isinstance(entry, schedulers.ModelEntry)


def test_scheduler_model_schedules_remains_a_tuple():
    assert schedulers.ModelEntry.model_schedules == (
        (schedules.crontab, helpers.crontabschedule_model, "crontab"),
        (schedules.schedule, helpers.intervalschedule_model, "interval"),
        (schedules.solar, helpers.solarschedule_model, "solar"),
        (schedulers.clocked, helpers.clockedschedule_model, "clocked"),
    )


def test_scheduler_model_schedules_resolve_schedule_models_lazily():
    class ActiveCrontabSchedule:
        pass

    class ActiveIntervalSchedule:
        pass

    class ActiveSolarSchedule:
        pass

    class ActiveClockedSchedule:
        pass

    class ActiveModelEntry(schedulers.ModelEntry):
        model_schedules = (
            (schedules.crontab, lambda: ActiveCrontabSchedule, "crontab"),
            (schedules.schedule, lambda: ActiveIntervalSchedule, "interval"),
            (schedules.solar, lambda: ActiveSolarSchedule, "solar"),
            (schedulers.clocked, lambda: ActiveClockedSchedule, "clocked"),
        )

    assert tuple(ActiveModelEntry._model_schedules()) == (
        (schedules.crontab, ActiveCrontabSchedule, "crontab"),
        (schedules.schedule, ActiveIntervalSchedule, "interval"),
        (schedules.solar, ActiveSolarSchedule, "solar"),
        (schedulers.clocked, ActiveClockedSchedule, "clocked"),
    )


def test_scheduler_model_schedules_support_concrete_model_classes():
    class ActiveCrontabSchedule:
        pass

    class ActiveModelEntry(schedulers.ModelEntry):
        model_schedules = (
            (schedules.crontab, ActiveCrontabSchedule, "crontab"),
        )

    assert tuple(ActiveModelEntry._model_schedules()) == (
        (schedules.crontab, ActiveCrontabSchedule, "crontab"),
    )


def test_database_scheduler_resolves_models_lazily(monkeypatch):
    class ActivePeriodicTask:
        pass

    class ActivePeriodicTasks:
        pass

    scheduler = object.__new__(schedulers.DatabaseScheduler)
    monkeypatch.setattr(
        helpers, "periodictask_model", lambda: ActivePeriodicTask
    )
    monkeypatch.setattr(
        helpers, "periodictasks_model", lambda: ActivePeriodicTasks
    )

    assert scheduler.Model is ActivePeriodicTask
    assert scheduler.Changes is ActivePeriodicTasks


def test_database_scheduler_crontab_queries_resolve_model_lazily(monkeypatch):
    manager = Mock()

    class ActiveCrontabSchedule:
        objects = manager

    scheduler = object.__new__(schedulers.DatabaseScheduler)
    monkeypatch.setattr(
        helpers, "crontabschedule_model", lambda: ActiveCrontabSchedule
    )

    scheduler._get_unique_timezone_names()

    manager.values_list.assert_called_once_with("timezone", flat=True)
