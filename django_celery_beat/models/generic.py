from .abstract import (AbstractClockedSchedule, AbstractCrontabSchedule,
                       AbstractIntervalSchedule, AbstractPeriodicTask,
                       AbstractPeriodicTasks, AbstractSolarSchedule)


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
    """Schedule triggered at a fixed date and time."""

    class Meta(AbstractClockedSchedule.Meta):
        """Table information."""

        abstract = False


class CrontabSchedule(AbstractCrontabSchedule):
    """Schedule with cron-style syntax."""

    class Meta(AbstractCrontabSchedule.Meta):
        """Table information."""

        abstract = False


class PeriodicTask(AbstractPeriodicTask):
    """Periodic task scheduling model."""

    class Meta(AbstractPeriodicTask.Meta):
        """Table information."""

        abstract = False


class PeriodicTasks(AbstractPeriodicTasks):
    """Helper table for tracking updates to periodic tasks."""

    class Meta(AbstractPeriodicTasks.Meta):
        abstract = False
