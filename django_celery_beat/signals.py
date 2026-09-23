"""Django Application signals."""
from .utils import clocked_due_after_next_sync


def signals_connect():
    """Connect to signals."""
    from django.db.models import signals  # noqa: PLC0415

    from .models import (ClockedSchedule, CrontabSchedule,  # noqa: PLC0415
                         IntervalSchedule, PeriodicTask, PeriodicTasks,
                         SolarSchedule)

    signals.post_save.connect(
        periodic_task_post_save, sender=PeriodicTask
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
        clocked_schedule_post_save, sender=ClockedSchedule
    )
    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=ClockedSchedule
    )


def periodic_task_post_save(sender, instance, raw, **kwargs):
    # Fixture loading uses raw=True and skips PeriodicTask.save().
    # Normal saves call PeriodicTasks.changed() directly in save().
    if raw:
        from .models import PeriodicTasks  # noqa: PLC0415

        PeriodicTasks.changed(instance)


def clocked_schedule_post_save(sender, instance, created, **kwargs):
    if created and clocked_due_after_next_sync(instance.clocked_time):
        # No forced reload needed: a regular sync will happen before this task is due
        return
    from .models import PeriodicTasks  # noqa: PLC0415
    PeriodicTasks.update_changed()
