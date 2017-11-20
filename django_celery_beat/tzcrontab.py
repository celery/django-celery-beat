"""Timezone aware Cron schedule Implementation."""
from __future__ import absolute_import, unicode_literals


from celery import schedules
from celery.utils.time import ffwd

from collections import namedtuple
import datetime
import pytz


schedstate = namedtuple('schedstate', ('is_due', 'next'))


class TzAwareCrontab(schedules.crontab):
    """Timezone Aware Crontab

    This class inherits from the Celery.schedules.crontab and add a timezone field ('tz') set to UTC
    by default

    """

    def __init__(self, minute='*', hour='*', day_of_week='*', day_of_month='*', month_of_year='*', tz=pytz.utc, app=None):
        """Overwrite Crontab constructor to include a timezone argument

        """
        self.tz = tz

        nowfun = lambda: self.tz.normalize(pytz.utc.localize(datetime.datetime.utcnow()))

        super(TzAwareCrontab, self).__init__(minute=minute, hour=hour, day_of_week=day_of_week, 
                    day_of_month=day_of_month, month_of_year=month_of_year, nowfun=nowfun, app=app)


    def is_due(self, last_run_at):
        """Calculate when the next run will take place
        
        Return tuple of ``(is_due, next_time_to_check)``.

        The last_run_at argument needs to be timezone aware.

        Notes:
            - next time to check is in seconds.
            - ``(True, 20)``, means the task should be run now, and the next
                time to check is in 20 seconds.
            - ``(False, 12.3)``, means the task is not due, but that the
              scheduler should check again in 12.3 seconds.
        The next time to check is used to save energy/CPU cycles,
        it does not need to be accurate but will influence the precision
        of your schedule.  You must also keep in mind
        the value of :setting:`beat_max_loop_interval`,
        that decides the maximum number of seconds the scheduler can
        sleep between re-checking the periodic task intervals.  So if you
        have a task that changes schedule at run-time then your next_run_at
        check will decide how long it will take before a change to the
        schedule takes effect.  The max loop interval takes precedence
        over the next check at value returned.
        .. admonition:: Scheduler max interval variance
            The default max loop interval may vary for different schedulers.
            For the default scheduler the value is 5 minutes, but for example
            the :pypi:`django-celery-beat` database scheduler the value
            is 5 seconds.

        """
        # convert last_run_at to the schedule timezone
        last_run_at = last_run_at.astimezone(self.tz)

        rem_delta = self.remaining_estimate(last_run_at)
        rem = max(rem_delta.total_seconds(), 0)
        due = rem == 0
        if due:
            rem_delta = self.remaining_estimate(self.now())
            rem = max(rem_delta.total_seconds(), 0)
        return schedstate(due, rem)


    # Needed to support pickling
    def __repr__(self):
        return """<crontab: {0._orig_minute} {0._orig_hour} {0._orig_day_of_week} {0._orig_day_of_month} {0._orig_month_of_year} (m/h/d/dM/MY), {0.tz}>""".format(self)

    def __reduce__(self):
        return (self.__class__, (self._orig_minute,
                                 self._orig_hour,
                                 self._orig_day_of_week,
                                 self._orig_day_of_month,
                                 self._orig_month_of_year,
                                 self.tz), None)

    def __eq__(self, other):
        if isinstance(other, schedules.crontab):
            return (other.month_of_year == self.month_of_year and
                    other.day_of_month == self.day_of_month and
                    other.day_of_week == self.day_of_week and
                    other.hour == self.hour and
                    other.minute == self.minute and
                    other.tz == self.tz)
        return NotImplemented