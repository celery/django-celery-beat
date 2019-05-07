"""Clocked schedule Implementation."""
from __future__ import absolute_import, unicode_literals


from celery import schedules
from celery.utils.time import maybe_make_aware
from collections import namedtuple


schedstate = namedtuple('schedstate', ('is_due', 'next'))


class clocked(schedules.BaseSchedule):
    """clocked schedule.

    It depend on PeriodicTask once_off
    """

    def __init__(self, clocked_time, enabled=True,
                 model=None, nowfun=None, app=None):
        """Initialize clocked."""
        self.clocked_time = maybe_make_aware(clocked_time)
        self.enabled = enabled
        self.model = model
        super(clocked, self).__init__(nowfun=nowfun, app=app)

    def remaining_estimate(self, last_run_at):
        return self.clocked_time - self.now()

    def is_due(self, last_run_at):
        # actually last run at is useless
        last_run_at = maybe_make_aware(last_run_at)
        rem_delta = self.remaining_estimate(last_run_at)
        remaining_s = max(rem_delta.total_seconds(), 0)
        if not self.enabled:
            return schedstate(is_due=False, next=None)
        if remaining_s == 0:
            if self.model:
                self.model.enabled = False
                self.model.save()
            return schedstate(is_due=True, next=None)
        return schedstate(is_due=False, next=remaining_s)

    def __repr__(self):
        return '<clocked: {} {}>'.format(self.clocked_time, self.enabled)

    def __eq__(self, other):
        if isinstance(other, clocked):
            return self.clocked_time == other.clocked_time and \
                self.enabled == other.enabled
        return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __reduce__(self):
        return self.__class__, (self.clocked_time, self.nowfun)
