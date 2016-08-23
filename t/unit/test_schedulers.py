from __future__ import absolute_import, unicode_literals

import pytest

from datetime import datetime, timedelta
from itertools import count

from celery.five import monotonic, text_t
from celery.schedules import schedule, crontab

from django_celery_beat import schedulers
from django_celery_beat.models import (
    PeriodicTask, PeriodicTasks, IntervalSchedule, CrontabSchedule,
)

_ids = count(0)


@pytest.fixture(autouse=True)
def no_multiprocessing_finalizers(patching):
    patching('multiprocessing.util.Finalize')
    patching('django_celery_beat.schedulers.Finalize')


class EntryTrackSave(schedulers.ModelEntry):

    def __init__(self, *args, **kwargs):
        self.saved = 0
        super(EntryTrackSave, self).__init__(*args, **kwargs)

    def save(self):
        self.saved += 1
        super(EntryTrackSave, self).save()


class EntrySaveRaises(schedulers.ModelEntry):

    def save(self):
        raise RuntimeError('this is expected')


class TrackingScheduler(schedulers.DatabaseScheduler):
    Entry = EntryTrackSave

    def __init__(self, *args, **kwargs):
        self.flushed = 0
        schedulers.DatabaseScheduler.__init__(self, *args, **kwargs)

    def sync(self):
        self.flushed += 1
        schedulers.DatabaseScheduler.sync(self)


@pytest.mark.django_db()
class SchedulerCase:

    def create_model_interval(self, schedule, **kwargs):
        interval = IntervalSchedule.from_schedule(schedule)
        interval.save()
        return self.create_model(interval=interval, **kwargs)

    def create_model_crontab(self, schedule, **kwargs):
        crontab = CrontabSchedule.from_schedule(schedule)
        crontab.save()
        return self.create_model(crontab=crontab, **kwargs)

    def create_model(self, Model=PeriodicTask, **kwargs):
        entry = dict(
            name='thefoo{0}'.format(next(_ids)),
            task='djcelery.unittest.add{0}'.format(next(_ids)),
            args='[2, 2]',
            kwargs='{"callback": "foo"}',
            queue='xaz',
            routing_key='cpu',
            exchange='foo',
        )
        return Model(**dict(entry, **kwargs))


@pytest.mark.django_db()
class test_ModelEntry(SchedulerCase):
    Entry = EntryTrackSave

    def test_entry(self):
        m = self.create_model_interval(schedule(timedelta(seconds=10)))
        e = self.Entry(m, app=self.app)

        assert e.args == [2, 2]
        assert e.kwargs == {'callback': 'foo'}
        assert e.schedule
        assert e.total_run_count == 0
        assert isinstance(e.last_run_at, datetime)
        assert e.options['queue'] == 'xaz'
        assert e.options['exchange'] == 'foo'
        assert e.options['routing_key'] == 'cpu'

        right_now = self.app.now()
        m2 = self.create_model_interval(
            schedule(timedelta(seconds=10)),
            last_run_at=right_now,
        )
        assert m2.last_run_at
        e2 = self.Entry(m2, app=self.app)
        assert e2.last_run_at is right_now

        e3 = e2.next()
        assert e3.last_run_at > e2.last_run_at
        assert e3.total_run_count == 1


@pytest.mark.django_db()
class test_DatabaseScheduler(SchedulerCase):
    Scheduler = TrackingScheduler

    @pytest.mark.django_db()
    @pytest.fixture(autouse=True)
    def setup_scheduler(self, app):
        self.app = app
        self.app.conf.beat_schedule = {}

        self.m1 = self.create_model_interval(
            schedule(timedelta(seconds=10)))
        self.m1.save()
        self.m1.refresh_from_db()
        self.m2 = self.create_model_interval(
            schedule(timedelta(minutes=20)))
        self.m2.save()
        self.m2.refresh_from_db()
        self.m3 = self.create_model_crontab(
            crontab(minute='2,4,5'))
        self.m3.save()
        self.m3.refresh_from_db()

        self.s = self.Scheduler(app=self.app)

    def test_constructor(self):
        assert isinstance(self.s._dirty, set)
        assert self.s._last_sync is None
        assert self.s.sync_every

    def test_all_as_schedule(self):
        sched = self.s.schedule
        assert sched
        assert len(sched) == 4
        assert 'celery.backend_cleanup' in sched
        for n, e in sched.items():
            assert isinstance(e, self.s.Entry)

    def test_schedule_changed(self):
        self.m2.args = '[16, 16]'
        self.m2.save()
        e2 = self.s.schedule[self.m2.name]
        assert e2.args == [16, 16]

        self.m1.args = '[32, 32]'
        self.m1.save()
        e1 = self.s.schedule[self.m1.name]
        assert e1.args == [32, 32]
        e1 = self.s.schedule[self.m1.name]
        assert e1.args == [32, 32]

        self.m3.delete()
        with pytest.raises(KeyError):
            self.s.schedule.__getitem__(self.m3.name)

    def test_should_sync(self):
        assert self.s.should_sync()
        self.s._last_sync = monotonic()
        assert not self.s.should_sync()
        self.s._last_sync -= self.s.sync_every
        assert self.s.should_sync()

    def test_reserve(self):
        e1 = self.s.schedule[self.m1.name]
        self.s.schedule[self.m1.name] = self.s.reserve(e1)
        assert self.s.flushed == 1

        e2 = self.s.schedule[self.m2.name]
        self.s.schedule[self.m2.name] = self.s.reserve(e2)
        assert self.s.flushed == 1
        assert self.m2.name in self.s._dirty

    def test_sync_saves_last_run_at(self):
        e1 = self.s.schedule[self.m2.name]
        last_run = e1.last_run_at
        last_run2 = last_run - timedelta(days=1)
        e1.model.last_run_at = last_run2
        self.s._dirty.add(self.m2.name)
        self.s.sync()

        e2 = self.s.schedule[self.m2.name]
        assert e2.last_run_at == last_run2

    def test_sync_syncs_before_save(self):
        # Get the entry for m2
        e1 = self.s.schedule[self.m2.name]

        # Increment the entry (but make sure it doesn't sync)
        self.s._last_sync = monotonic()
        e2 = self.s.schedule[e1.name] = self.s.reserve(e1)
        assert self.s.flushed == 1

        # Fetch the raw object from db, change the args
        # and save the changes.
        m2 = PeriodicTask.objects.get(pk=self.m2.pk)
        m2.args = '[16, 16]'
        m2.save()

        # get_schedule should now see the schedule has changed.
        # and also sync the dirty objects.
        e3 = self.s.schedule[self.m2.name]
        assert self.s.flushed == 2
        assert e3.last_run_at == e2.last_run_at
        assert e3.args == [16, 16]

    def test_sync_not_dirty(self):
        self.s._dirty.clear()
        self.s.sync()

    def test_sync_object_gone(self):
        self.s._dirty.add('does-not-exist')
        self.s.sync()

    def test_sync_rollback_on_save_error(self):
        self.s.schedule[self.m1.name] = EntrySaveRaises(self.m1, app=self.app)
        self.s._dirty.add(self.m1.name)
        with pytest.raises(RuntimeError):
            self.s.sync()


@pytest.mark.django_db()
class test_models(SchedulerCase):

    def test_IntervalSchedule_unicode(self):
        assert (text_t(IntervalSchedule(every=1, period='seconds')) ==
                'every second')
        assert (text_t(IntervalSchedule(every=10, period='seconds')) ==
                'every 10 seconds')

    def test_CrontabSchedule_unicode(self):
        assert text_t(CrontabSchedule(
            minute=3,
            hour=3,
            day_of_week=None,
        )) == '3 3 * * * (m/h/d/dM/MY)'
        assert text_t(CrontabSchedule(
            minute=3,
            hour=3,
            day_of_week='tue',
            day_of_month='*/2',
            month_of_year='4,6',
        )) == '3 3 tue */2 4,6 (m/h/d/dM/MY)'

    def test_PeriodicTask_unicode_interval(self):
        p = self.create_model_interval(schedule(timedelta(seconds=10)))
        assert text_t(p) == '{0}: every 10.0 seconds'.format(p.name)

    def test_PeriodicTask_unicode_crontab(self):
        p = self.create_model_crontab(crontab(
            hour='4, 5',
            day_of_week='4, 5',
        ))
        assert text_t(p) == '{0}: * 4,5 4,5 * * (m/h/d/dM/MY)'.format(p.name)

    def test_PeriodicTask_schedule_property(self):
        p1 = self.create_model_interval(schedule(timedelta(seconds=10)))
        s1 = p1.schedule
        assert s1.run_every.total_seconds() == 10

        p2 = self.create_model_crontab(crontab(
            hour='4, 5',
            minute='10,20,30',
            day_of_month='1-7',
            month_of_year='*/3',
        ))
        s2 = p2.schedule
        assert s2.hour == {4, 5}
        assert s2.minute == {10, 20, 30}
        assert s2.day_of_week == {0, 1, 2, 3, 4, 5, 6}
        assert s2.day_of_month == {1, 2, 3, 4, 5, 6, 7}
        assert s2.month_of_year == {1, 4, 7, 10}

    def test_PeriodicTask_unicode_no_schedule(self):
        p = self.create_model()
        assert text_t(p) == '{0}: {{no schedule}}'.format(p.name)

    def test_CrontabSchedule_schedule(self):
        s = CrontabSchedule(
            minute='3, 7',
            hour='3, 4',
            day_of_week='*',
            day_of_month='1, 16',
            month_of_year='1, 7',
        )
        assert s.schedule.minute == {3, 7}
        assert s.schedule.hour == {3, 4}
        assert s.schedule.day_of_week == {0, 1, 2, 3, 4, 5, 6}
        assert s.schedule.day_of_month == {1, 16}
        assert s.schedule.month_of_year == {1, 7}


@pytest.mark.django_db()
class test_model_PeriodicTasks(SchedulerCase):

    def test_track_changes(self):
        assert PeriodicTasks.last_change() is None
        m1 = self.create_model_interval(schedule(timedelta(seconds=10)))
        m1.save()
        x = PeriodicTasks.last_change()
        assert x
        m1.args = '(23, 24)'
        m1.save()
        y = PeriodicTasks.last_change()
        assert y
        assert y > x
