"""Django Application signals."""


def signals_connect():
    """Connect to signals."""
    from django.db.models import signals  # noqa: PLC0415

    from .helpers import (  # noqa: PLC0415
        clockedschedule_model,
        crontabschedule_model,
        intervalschedule_model,
        periodictask_model,
        periodictasks_model,
        solarschedule_model,
    )

    ClockedSchedule = clockedschedule_model()
    CrontabSchedule = crontabschedule_model()
    IntervalSchedule = intervalschedule_model()
    PeriodicTask = periodictask_model()
    PeriodicTasks = periodictasks_model()
    SolarSchedule = solarschedule_model()

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
