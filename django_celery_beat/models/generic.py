from django.db.models import signals

from .abstract import (
    AbstractClockedSchedule,
    AbstractCrontabSchedule,
    AbstractIntervalSchedule,
    AbstractPeriodicTask,
    AbstractPeriodicTasks,
    AbstractSolarSchedule,
)
from ..querysets import PeriodicTaskQuerySet


class SolarSchedule(AbstractSolarSchedule):
    """Schedule following astronomical patterns."""

    class Meta(AbstractSolarSchedule.Meta):
        """Table information."""

        abstract = False


class IntervalSchedule(AbstractIntervalSchedule):
    """Schedule with a fixed interval."""

    class Meta(AbstractIntervalSchedule.Meta):
        """Table information."""

        abstract = False


class ClockedSchedule(AbstractClockedSchedule):
    """Schedule with a fixed interval."""

    class Meta(AbstractClockedSchedule.Meta):
        """Table information."""

        abstract = False


class CrontabSchedule(AbstractCrontabSchedule):
    """Schedule with cron-style syntax."""

    class Meta(AbstractCrontabSchedule.Meta):
        """Table information."""

        abstract = False


class PeriodicTask(AbstractPeriodicTask):
    """Interal task scheduling class."""

    objects = PeriodicTaskQuerySet.as_manager()

    class Meta(AbstractPeriodicTask.Meta):
        """Table information."""

        abstract = False


class PeriodicTasks(AbstractPeriodicTasks):
    """Helper table for tracking updates to periodic tasks."""

    class Meta(AbstractPeriodicTasks.Meta):
        abstract = False


signals.pre_delete.connect(PeriodicTasks.changed, sender=PeriodicTask)
signals.pre_save.connect(PeriodicTasks.changed, sender=PeriodicTask)
signals.pre_delete.connect(PeriodicTasks.update_changed, sender=IntervalSchedule)
signals.post_save.connect(PeriodicTasks.update_changed, sender=IntervalSchedule)
signals.post_delete.connect(PeriodicTasks.update_changed, sender=CrontabSchedule)
signals.post_save.connect(PeriodicTasks.update_changed, sender=CrontabSchedule)
signals.post_delete.connect(PeriodicTasks.update_changed, sender=SolarSchedule)
signals.post_save.connect(PeriodicTasks.update_changed, sender=SolarSchedule)
signals.post_delete.connect(PeriodicTasks.update_changed, sender=ClockedSchedule)
signals.post_save.connect(PeriodicTasks.update_changed, sender=ClockedSchedule)
