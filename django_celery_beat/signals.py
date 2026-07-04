"""Django Application signals."""


def signals_connect():
    """Connect to signals."""
    from django.db.models import signals  # noqa: PLC0415

    from .models import (ClockedSchedule, CrontabSchedule,  # noqa: PLC0415
                         IntervalSchedule, PeriodicTask, PeriodicTasks,
                         SolarSchedule)

    signals.post_delete.connect(
        PeriodicTasks.changed, sender=PeriodicTask
    )

    signals.pre_delete.connect(
        PeriodicTasks.update_changed, sender=IntervalSchedule
    )

    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=CrontabSchedule
    )

    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=SolarSchedule
    )

    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=ClockedSchedule
    )
