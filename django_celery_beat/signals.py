"""Django Application signals."""


def signals_connect():
    """Connect to signals."""
    from django.db.models import signals  # noqa: PLC0415

    from django_celery_beat import helpers  # noqa: PLC0415

    ClockedSchedule = helpers.clockedschedule_model()
    CrontabSchedule = helpers.crontabschedule_model()
    IntervalSchedule = helpers.intervalschedule_model()
    PeriodicTask = helpers.periodictask_model()
    PeriodicTasks = helpers.periodictasks_model()
    SolarSchedule = helpers.solarschedule_model()

    signals.pre_save.connect(
        PeriodicTasks.changed, sender=PeriodicTask
    )
    signals.pre_delete.connect(
        PeriodicTasks.changed, sender=PeriodicTask
    )

    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=IntervalSchedule
    )
    signals.pre_delete.connect(
        PeriodicTasks.update_changed, sender=IntervalSchedule
    )

    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=CrontabSchedule
    )
    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=CrontabSchedule
    )

    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=SolarSchedule
    )
    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=SolarSchedule
    )

    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=ClockedSchedule
    )
    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=ClockedSchedule
    )
