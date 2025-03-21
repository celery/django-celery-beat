import math
import os
import time
from datetime import datetime, timedelta
from itertools import count
from time import monotonic

import pytest
from celery.schedules import crontab, schedule, solar
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, override_settings
from django.utils import timezone

from django_celery_beat import schedulers
from django_celery_beat.admin import PeriodicTaskAdmin
from django_celery_beat.clockedschedule import clocked
from django_celery_beat.models import (DAYS, ClockedSchedule, CrontabSchedule,
                                       IntervalSchedule, PeriodicTask,
                                       PeriodicTasks, SolarSchedule)
from django_celery_beat.utils import NEVER_CHECK_TIMEOUT, make_aware

_ids = count(0)


@pytest.fixture(autouse=True)
def no_multiprocessing_finalizers(patching):
    patching('multiprocessing.util.Finalize')
    patching('django_celery_beat.schedulers.Finalize')


class EntryTrackSave(schedulers.ModelEntry):

    def __init__(self, *args, **kwargs):
        self.saved = 0
        super().__init__(*args, **kwargs)

    def save(self):
        self.saved += 1
        super().save()


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


@pytest.mark.django_db
class SchedulerCase:

    def create_model_interval(self, schedule, **kwargs):
        interval = IntervalSchedule.from_schedule(schedule)
        interval.save()
        return self.create_model(interval=interval, **kwargs)

    def create_model_crontab(self, schedule, **kwargs):
        crontab = CrontabSchedule.from_schedule(schedule)
        crontab.save()
        return self.create_model(crontab=crontab, **kwargs)

    def create_model_solar(self, schedule, **kwargs):
        solar = SolarSchedule.from_schedule(schedule)
        solar.save()
        return self.create_model(solar=solar, **kwargs)

    def create_model_clocked(self, schedule, **kwargs):
        clocked = ClockedSchedule.from_schedule(schedule)
        clocked.save()
        return self.create_model(clocked=clocked, one_off=True, **kwargs)

    def create_conf_entry(self):
        name = f'thefoo{next(_ids)}'
        return name, dict(
            task=f'djcelery.unittest.add{next(_ids)}',
            schedule=timedelta(0, 600),
            args=(),
            relative=False,
            kwargs={},
            options={'queue': 'extra_queue'}
        )

    def create_model(self, Model=PeriodicTask, **kwargs):
        entry = dict(
            name=f'thefoo{next(_ids)}',
            task=f'djcelery.unittest.add{next(_ids)}',
            args='[2, 2]',
            kwargs='{"callback": "foo"}',
            queue='xaz',
            routing_key='cpu',
            priority=1,
            headers='{"_schema_name": "foobar"}',
            exchange='foo',
        )
        return Model(**dict(entry, **kwargs))

    def create_interval_schedule(self):
        return IntervalSchedule.objects.create(every=10, period=DAYS)

    def create_crontab_schedule(self):
        return CrontabSchedule.objects.create()


@pytest.mark.django_db
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
        assert e.options['priority'] == 1
        assert e.options['headers']['_schema_name'] == 'foobar'
        assert e.options['headers']['periodic_task_name'] == m.name

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

    @override_settings(
        USE_TZ=False,
        DJANGO_CELERY_BEAT_TZ_AWARE=False
    )
    @pytest.mark.usefixtures('depends_on_current_app')
    @timezone.override('Europe/Berlin')
    @pytest.mark.celery(timezone='Europe/Berlin')
    def test_entry_is_due__no_use_tz(self):
        old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Berlin"
        if hasattr(time, "tzset"):
            time.tzset()
        assert self.app.timezone.key == 'Europe/Berlin'

        # simulate last_run_at from DB - not TZ aware but localtime
        right_now = datetime.utcnow()

        m = self.create_model_crontab(
            crontab(minute='*/10'),
            last_run_at=right_now,
        )
        e = self.Entry(m, app=self.app)

        assert e.is_due().is_due is False
        assert e.is_due().next <= 600  # 10 minutes; see above
        if old_tz is not None:
            os.environ["TZ"] = old_tz
        else:
            del os.environ["TZ"]
        if hasattr(time, "tzset"):
            time.tzset()

    @override_settings(
        USE_TZ=False,
        DJANGO_CELERY_BEAT_TZ_AWARE=False
    )
    @pytest.mark.usefixtures('depends_on_current_app')
    @timezone.override('Europe/Berlin')
    @pytest.mark.celery(timezone='Europe/Berlin')
    def test_entry_and_model_last_run_at_with_utc_no_use_tz(self, monkeypatch):
        old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Berlin"
        if hasattr(time, "tzset"):
            time.tzset()
        assert self.app.timezone.key == 'Europe/Berlin'
        # simulate last_run_at from DB - not TZ aware but localtime
        right_now = datetime.utcnow()
        # make sure to use fixed date time
        monkeypatch.setattr(self.Entry, '_default_now', lambda o: right_now)
        m = self.create_model_crontab(
            crontab(minute='*/10')
        )
        m.save()
        e = self.Entry(m, app=self.app)
        e.save()
        m.refresh_from_db()

        assert m.last_run_at == e.last_run_at

        if old_tz is not None:
            os.environ["TZ"] = old_tz
        else:
            del os.environ["TZ"]
        if hasattr(time, "tzset"):
            time.tzset()

    @override_settings(
        USE_TZ=False,
        DJANGO_CELERY_BEAT_TZ_AWARE=False
    )
    @pytest.mark.usefixtures('depends_on_current_app')
    @timezone.override('Europe/Berlin')
    @pytest.mark.celery(timezone='Europe/Berlin')
    def test_entry_and_model_last_run_at_when_model_changed(self, monkeypatch):
        old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Berlin"
        if hasattr(time, "tzset"):
            time.tzset()
        assert self.app.timezone.key == 'Europe/Berlin'
        # simulate last_run_at from DB - not TZ aware but localtime
        right_now = datetime.utcnow()
        # make sure to use fixed date time
        monkeypatch.setattr(self.Entry, '_default_now', lambda o: right_now)
        m = self.create_model_crontab(
            crontab(minute='*/10')
        )
        m.save()
        e = self.Entry(m, app=self.app)
        e.save()
        m.refresh_from_db()

        # The just created model has no value for date_changed
        # so last_run_at should be set to the Entry._default_now()
        assert m.last_run_at == e.last_run_at

        # If the model has been updated and the entry.last_run_at is None,
        # entry.last_run_at should be set to the value of model.date_changed.
        # see #717
        m2 = self.create_model_crontab(
            crontab(minute='*/10')
        )
        m2.save()
        m2.refresh_from_db()
        assert m2.date_changed is not None
        e2 = self.Entry(m2, app=self.app)
        e2.save()
        assert m2.last_run_at == m2.date_changed

        if old_tz is not None:
            os.environ["TZ"] = old_tz
        else:
            del os.environ["TZ"]
        if hasattr(time, "tzset"):
            time.tzset()

    @override_settings(
        USE_TZ=False,
        DJANGO_CELERY_BEAT_TZ_AWARE=False,
        TIME_ZONE="Europe/Berlin",
        CELERY_TIMEZONE="America/New_York"
    )
    @pytest.mark.usefixtures('depends_on_current_app')
    @timezone.override('Europe/Berlin')
    @pytest.mark.celery(timezone='America/New_York')
    def test_entry_is_due__celery_timezone_doesnt_match_time_zone(self):
        old_tz = os.environ.get("TZ")
        os.environ["TZ"] = "Europe/Berlin"
        if hasattr(time, "tzset"):
            time.tzset()
        assert self.app.timezone.key == 'America/New_York'

        # simulate last_run_at all none, doing the same thing that
        # _default_now() would do
        right_now = datetime.utcnow()

        m = self.create_model_crontab(
            crontab(minute='*/10'),
            last_run_at=right_now,
        )
        e = self.Entry(m, app=self.app)

        assert e.is_due().is_due is False
        assert e.is_due().next <= 600  # 10 minutes; see above
        if old_tz is not None:
            os.environ["TZ"] = old_tz
        else:
            del os.environ["TZ"]
        if hasattr(time, "tzset"):
            time.tzset()

    def test_task_with_start_time(self):
        interval = 10
        right_now = self.app.now()
        one_interval_ago = right_now - timedelta(seconds=interval)
        m = self.create_model_interval(schedule(timedelta(seconds=interval)),
                                       start_time=right_now,
                                       last_run_at=one_interval_ago)
        e = self.Entry(m, app=self.app)
        isdue, delay = e.is_due()
        assert isdue
        assert delay == interval

        tomorrow = right_now + timedelta(days=1)
        m2 = self.create_model_interval(schedule(timedelta(seconds=interval)),
                                        start_time=tomorrow,
                                        last_run_at=one_interval_ago)
        e2 = self.Entry(m2, app=self.app)
        isdue, delay = e2.is_due()
        assert not isdue
        assert delay == math.ceil((tomorrow - right_now).total_seconds())

    def test_one_off_task(self):
        interval = 10
        right_now = self.app.now()
        one_interval_ago = right_now - timedelta(seconds=interval)
        m = self.create_model_interval(schedule(timedelta(seconds=interval)),
                                       one_off=True,
                                       last_run_at=one_interval_ago,
                                       total_run_count=0)
        e = self.Entry(m, app=self.app)
        isdue, delay = e.is_due()
        assert isdue
        assert delay == interval

        m2 = self.create_model_interval(schedule(timedelta(seconds=interval)),
                                        one_off=True,
                                        last_run_at=one_interval_ago,
                                        total_run_count=1)
        e2 = self.Entry(m2, app=self.app)
        isdue, delay = e2.is_due()
        assert not isdue
        assert delay == NEVER_CHECK_TIMEOUT

    def test_task_with_expires(self):
        interval = 10
        right_now = self.app.now()
        one_second_later = right_now + timedelta(seconds=1)
        m = self.create_model_interval(schedule(timedelta(seconds=interval)),
                                       start_time=right_now,
                                       expires=one_second_later)
        e = self.Entry(m, app=self.app)
        isdue, delay = e.is_due()
        assert isdue
        assert delay == interval

        m2 = self.create_model_interval(schedule(timedelta(seconds=interval)),
                                        start_time=right_now,
                                        expires=right_now)
        e2 = self.Entry(m2, app=self.app)
        isdue, delay = e2.is_due()
        assert not isdue
        assert delay == NEVER_CHECK_TIMEOUT

        one_second_ago = right_now - timedelta(seconds=1)
        m2 = self.create_model_interval(schedule(timedelta(seconds=interval)),
                                        start_time=right_now,
                                        expires=one_second_ago)
        e2 = self.Entry(m2, app=self.app)
        isdue, delay = e2.is_due()
        assert not isdue
        assert delay == NEVER_CHECK_TIMEOUT


@pytest.mark.django_db
class test_DatabaseSchedulerFromAppConf(SchedulerCase):
    Scheduler = TrackingScheduler

    @pytest.mark.django_db
    @pytest.fixture(autouse=True)
    def setup_scheduler(self, app):
        self.app = app

        self.entry_name, entry = self.create_conf_entry()
        self.app.conf.beat_schedule = {self.entry_name: entry}
        self.m1 = PeriodicTask(name=self.entry_name,
                               interval=self.create_interval_schedule())

    def test_constructor(self):
        s = self.Scheduler(app=self.app)

        assert isinstance(s._dirty, set)
        assert s._last_sync is None
        assert s.sync_every

    def test_periodic_task_model_enabled_schedule(self):
        s = self.Scheduler(app=self.app)
        sched = s.schedule
        assert len(sched) == 2
        assert 'celery.backend_cleanup' in sched
        assert self.entry_name in sched
        for n, e in sched.items():
            assert isinstance(e, s.Entry)
            if n == 'celery.backend_cleanup':
                assert e.options['expires'] == 12 * 3600
                assert e.model.expires is None
                assert e.model.expire_seconds == 12 * 3600

    def test_periodic_task_model_disabled_schedule(self):
        self.m1.enabled = False
        self.m1.save()

        s = self.Scheduler(app=self.app)
        sched = s.schedule
        assert sched
        assert len(sched) == 1
        assert 'celery.backend_cleanup' in sched
        assert self.entry_name not in sched

    def test_periodic_task_model_schedule_type_change(self):
        self.m1.interval = None
        self.m1.crontab = self.create_crontab_schedule()
        self.m1.save()

        self.Scheduler(app=self.app)
        self.m1.refresh_from_db()
        assert self.m1.interval
        assert self.m1.crontab is None


@pytest.mark.django_db
class test_DatabaseScheduler(SchedulerCase):
    Scheduler = TrackingScheduler

    @pytest.mark.django_db
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

        self.m4 = self.create_model_solar(
            solar('solar_noon', 48.06, 12.86))
        self.m4.save()
        self.m4.refresh_from_db()

        # disabled, should not be in schedule
        self.m5 = self.create_model_interval(
            schedule(timedelta(seconds=1)))
        self.m5.enabled = False
        self.m5.save()

        # near future time (should be in schedule)
        now = datetime.now()
        two_minutes_later = now + timedelta(minutes=2)
        dt_aware = make_aware(
            datetime(
                day=two_minutes_later.day,
                month=two_minutes_later.month,
                year=two_minutes_later.year,
                hour=two_minutes_later.hour,
                minute=two_minutes_later.minute
            )
        )
        self.m6 = self.create_model_clocked(
            clocked(dt_aware)
        )
        self.m6.save()
        self.m6.refresh_from_db()

        # distant future time (should not be in schedule)
        ten_minutes_later = now + timedelta(minutes=10)
        distant_dt_aware = make_aware(
            datetime(
                day=ten_minutes_later.day,
                month=ten_minutes_later.month,
                year=ten_minutes_later.year,
                hour=ten_minutes_later.hour,
                minute=ten_minutes_later.minute
            )
        )
        self.m7 = self.create_model_clocked(
            clocked(distant_dt_aware)
        )
        self.m7.save()
        self.m7.refresh_from_db()

        now_hour = timezone.localtime(timezone.now()).hour
        # near future time (should be in schedule)
        self.m8 = self.create_model_crontab(
            crontab(hour=str(now_hour)))
        self.m8.save()
        self.m8.refresh_from_db()
        self.m9 = self.create_model_crontab(
            crontab(hour=str((now_hour + 1) % 24)))
        self.m9.save()
        self.m9.refresh_from_db()
        self.m10 = self.create_model_crontab(
            crontab(hour=str((now_hour - 1) % 24)))
        self.m10.save()
        self.m10.refresh_from_db()

        # distant future time (should not be in schedule)
        self.m11 = self.create_model_crontab(
            crontab(hour=str((now_hour + 2) % 24)))
        self.m11.save()
        self.m11.refresh_from_db()

        self.s = self.Scheduler(app=self.app)

    def test_constructor(self):
        assert isinstance(self.s._dirty, set)
        assert self.s._last_sync is None
        assert self.s.sync_every

    def test_all_as_schedule(self):
        sched = self.s.schedule
        assert sched
        assert len(sched) == 9
        assert 'celery.backend_cleanup' in sched
        for n, e in sched.items():
            assert isinstance(e, self.s.Entry)

    def test_get_excluded_hours_for_crontab_tasks(self):
        now_hour = timezone.localtime(timezone.now()).hour
        excluded_hours = self.s.get_excluded_hours_for_crontab_tasks()

        assert str(now_hour) not in excluded_hours
        assert str((now_hour + 1) % 24) not in excluded_hours
        assert str((now_hour - 1) % 24) not in excluded_hours
        assert str(4) not in excluded_hours

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

    def test_sync_not_saves_last_run_at_while_schedule_changed(self):
        # Update e1 last_run_at and add to dirty
        e1 = self.s.schedule[self.m2.name]
        time.sleep(3)
        e1.model.last_run_at = e1._default_now()
        self.s._dirty.add(e1.model.name)

        # Record e1 pre sync last_run_at
        e1_pre_sync_last_run_at = e1.model.last_run_at

        # Set schedule_changed() == True
        self.s._last_timestamp = monotonic()
        # Do sync
        self.s.sync()

        # Record e1 post sync last_run_at
        e1_m = PeriodicTask.objects.get(pk=e1.model.pk)
        e1_post_sync_last_run_at = e1_m.last_run_at

        # Check
        assert e1_pre_sync_last_run_at == e1_post_sync_last_run_at

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

    def test_periodic_task_disabled_and_enabled(self):
        # Get the entry for m2
        e1 = self.s.schedule[self.m2.name]

        # Increment the entry (but make sure it doesn't sync)
        self.s._last_sync = monotonic()
        self.s.schedule[e1.name] = self.s.reserve(e1)
        assert self.s.flushed == 1

        # Fetch the raw object from db, change the args
        # and save the changes.
        m2 = PeriodicTask.objects.get(pk=self.m2.pk)
        m2.enabled = False
        m2.save()

        # get_schedule should now see the schedule has changed.
        # and remove entry for m2
        assert self.m2.name not in self.s.schedule
        assert self.s.flushed == 2

        m2.enabled = True
        m2.save()

        # get_schedule should now see the schedule has changed.
        # and add entry for m2
        assert self.m2.name in self.s.schedule
        assert self.s.flushed == 3

    def test_periodic_task_disabled_while_reserved(self):
        # Get the entry for m2
        e1 = self.s.schedule[self.m2.name]

        # Increment the entry (but make sure it doesn't sync)
        self.s._last_sync = monotonic()
        e2 = self.s.schedule[e1.name] = self.s.reserve(e1)
        assert self.s.flushed == 1

        # Fetch the raw object from db, change the args
        # and save the changes.
        m2 = PeriodicTask.objects.get(pk=self.m2.pk)
        m2.enabled = False
        m2.save()

        # reserve is called because the task gets called from
        # tick after the database change is made
        self.s.reserve(e2)

        # get_schedule should now see the schedule has changed.
        # and remove entry for m2
        assert self.m2.name not in self.s.schedule
        assert self.s.flushed == 2

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

    def test_update_scheduler_heap_invalidation(self, monkeypatch):
        # mock "schedule_changed" to always trigger update for
        # all calls to schedule, as a change may occur at any moment
        monkeypatch.setattr(self.s, 'schedule_changed', lambda: True)
        self.s.tick()

    def test_heap_size_is_constant(self, monkeypatch):
        # heap size is constant unless the schedule changes
        monkeypatch.setattr(self.s, 'schedule_changed', lambda: True)
        expected_heap_size = len(self.s.schedule.values())
        self.s.tick()
        assert len(self.s._heap) == expected_heap_size
        self.s.tick()
        assert len(self.s._heap) == expected_heap_size

    def test_scheduler_schedules_equality_on_change(self, monkeypatch):
        monkeypatch.setattr(self.s, 'schedule_changed', lambda: False)
        assert self.s.schedules_equal(self.s.schedule, self.s.schedule)

        monkeypatch.setattr(self.s, 'schedule_changed', lambda: True)
        assert not self.s.schedules_equal(self.s.schedule, self.s.schedule)

    def test_heap_always_return_the_first_item(self):
        interval = 10

        s1 = schedule(timedelta(seconds=interval))
        m1 = self.create_model_interval(s1, enabled=False)
        m1.last_run_at = self.app.now() - timedelta(seconds=interval + 2)
        m1.save()
        m1.refresh_from_db()

        s2 = schedule(timedelta(seconds=interval))
        m2 = self.create_model_interval(s2, enabled=True)
        m2.last_run_at = self.app.now() - timedelta(seconds=interval + 1)
        m2.save()
        m2.refresh_from_db()

        e1 = EntryTrackSave(m1, self.app)
        # because the disabled task e1 runs first, e2 will never be executed
        e2 = EntryTrackSave(m2, self.app)

        s = self.Scheduler(app=self.app)
        s.schedule.clear()
        s.schedule[e1.name] = e1
        s.schedule[e2.name] = e2

        tried = set()
        for _ in range(len(s.schedule) * 8):
            tick_interval = s.tick()
            if tick_interval and tick_interval > 0.0:
                tried.add(s._heap[0].entry.name)
                time.sleep(tick_interval)
                if s.should_sync():
                    s.sync()
        assert len(tried) == 1 and tried == {e1.name}

    def test_starttime_trigger(self, monkeypatch):
        # Ensure there is no heap block in case of new task with start_time
        PeriodicTask.objects.all().delete()
        s = self.Scheduler(app=self.app)
        assert not s._heap
        m1 = self.create_model_interval(schedule(timedelta(seconds=3)))
        m1.save()
        s.tick()
        assert len(s._heap) == 2
        m2 = self.create_model_interval(
            schedule(timedelta(days=1)),
            start_time=make_aware(
                datetime.now() + timedelta(seconds=2)))
        m2.save()
        s.tick()
        assert s._heap[0][2].name == m2.name
        assert len(s._heap) == 3
        assert s._heap[0]
        time.sleep(2)
        s.tick()
        assert s._heap[0]
        assert s._heap[0][2].name == m1.name


@pytest.mark.django_db
class test_models(SchedulerCase):

    def test_IntervalSchedule_unicode(self):
        assert (str(IntervalSchedule(every=1, period='seconds'))
                == 'every second')
        assert (str(IntervalSchedule(every=10, period='seconds'))
                == 'every 10 seconds')

    def test_CrontabSchedule_unicode(self):
        assert str(CrontabSchedule(
            minute=3,
            hour=3,
            day_of_week=None,
        )) == '3 3 * * * (m/h/dM/MY/d) UTC'
        assert str(CrontabSchedule(
            minute=3,
            hour=3,
            day_of_week='tue',
            day_of_month='*/2',
            month_of_year='4,6',
        )) == '3 3 */2 4,6 tue (m/h/dM/MY/d) UTC'

    def test_PeriodicTask_unicode_interval(self):
        p = self.create_model_interval(schedule(timedelta(seconds=10)))
        assert str(p) == f'{p.name}: every 10.0 seconds'

    def test_PeriodicTask_unicode_crontab(self):
        p = self.create_model_crontab(crontab(
            hour='4, 5',
            day_of_week='4, 5',
        ))
        assert str(p) == """{}: * 4,5 * * 4,5 (m/h/dM/MY/d) UTC""".format(
            p.name
        )

    def test_PeriodicTask_unicode_solar(self):
        p = self.create_model_solar(
            solar('solar_noon', 48.06, 12.86), name='solar_event'
        )
        assert str(p) == 'solar_event: {} ({}, {})'.format(
            'Solar noon', '48.06', '12.86'
        )

    def test_PeriodicTask_unicode_clocked(self):
        time = make_aware(datetime.now())
        p = self.create_model_clocked(
            clocked(time), name='clocked_event'
        )
        assert str(p) == '{}: {}'.format(
            'clocked_event', str(time)
        )

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
        assert str(p) == f'{p.name}: {{no schedule}}'

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

    def test_CrontabSchedule_long_schedule(self):
        s = CrontabSchedule(
            minute=str(list(range(60)))[1:-1],
            hour=str(list(range(24)))[1:-1],
            day_of_week=str(list(range(7)))[1:-1],
            day_of_month=str(list(range(1, 32)))[1:-1],
            month_of_year=str(list(range(1, 13)))[1:-1]
        )
        assert s.schedule.minute == set(range(60))
        assert s.schedule.hour == set(range(24))
        assert s.schedule.day_of_week == set(range(7))
        assert s.schedule.day_of_month == set(range(1, 32))
        assert s.schedule.month_of_year == set(range(1, 13))
        fields = [
            'minute', 'hour', 'day_of_week', 'day_of_month', 'month_of_year'
        ]
        for field in fields:
            str_length = len(str(getattr(s.schedule, field)))
            field_length = s._meta.get_field(field).max_length
            assert str_length <= field_length

    def test_SolarSchedule_schedule(self):
        s = SolarSchedule(event='solar_noon', latitude=48.06, longitude=12.86)
        dt = datetime(day=26, month=7, year=2050, hour=1, minute=0)
        dt_lastrun = make_aware(dt)

        assert s.schedule is not None
        isdue, nextcheck = s.schedule.is_due(dt_lastrun)
        assert isdue is False  # False means task isn't due, but keep checking.
        assert (nextcheck > 0) and (isdue is False) or \
            (nextcheck == s.max_interval) and (isdue is True)

        s2 = SolarSchedule(event='solar_noon', latitude=48.06, longitude=12.86)
        dt2 = datetime(day=26, month=7, year=2000, hour=1, minute=0)
        dt2_lastrun = make_aware(dt2)

        assert s2.schedule is not None
        isdue2, nextcheck2 = s2.schedule.is_due(dt2_lastrun)
        assert isdue2 is True  # True means task is due and should run.
        assert (nextcheck2 > 0) and (isdue2 is True) or \
            (nextcheck2 == s2.max_interval) and (isdue2 is False)

    def test_ClockedSchedule_schedule(self):
        due_datetime = make_aware(datetime(day=26,
                                           month=7,
                                           year=3000,
                                           hour=1,
                                           minute=0))  # future time
        s = ClockedSchedule(clocked_time=due_datetime)
        dt = datetime(day=25, month=7, year=2050, hour=1, minute=0)
        dt_lastrun = make_aware(dt)

        assert s.schedule is not None
        isdue, nextcheck = s.schedule.is_due(dt_lastrun)
        assert isdue is False  # False means task isn't due, but keep checking.
        assert (nextcheck > 0) and (isdue is False) or \
            (nextcheck == s.max_interval) and (isdue is True)

        due_datetime = make_aware(datetime.now())
        s = ClockedSchedule(clocked_time=due_datetime)
        dt2_lastrun = make_aware(datetime.now())

        assert s.schedule is not None
        isdue2, nextcheck2 = s.schedule.is_due(dt2_lastrun)
        assert isdue2 is True  # True means task is due and should run.
        assert (nextcheck2 == NEVER_CHECK_TIMEOUT) and (isdue2 is True)


@pytest.mark.django_db
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


@pytest.mark.django_db
class test_modeladmin_PeriodicTaskAdmin(SchedulerCase):
    @pytest.mark.django_db
    @pytest.fixture(autouse=True)
    def setup_scheduler(self, app):
        self.app = app
        self.site = AdminSite()
        self.request_factory = RequestFactory()

        interval_schedule = self.create_interval_schedule()

        entry_name, entry = self.create_conf_entry()
        self.app.conf.beat_schedule = {entry_name: entry}
        self.m1 = PeriodicTask(name=entry_name, interval=interval_schedule)
        self.m1.task = 'celery.backend_cleanup'
        self.m1.save()

        entry_name, entry = self.create_conf_entry()
        self.app.conf.beat_schedule = {entry_name: entry}
        self.m2 = PeriodicTask(name=entry_name, interval=interval_schedule)
        self.m2.task = 'celery.backend_cleanup'
        self.m2.save()

    def patch_request(self, request):
        """patch request to allow for django messages storage"""
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request

    # don't hang if broker is down
    # https://github.com/celery/celery/issues/4627
    @pytest.mark.timeout(5)
    def test_run_task(self):
        ma = PeriodicTaskAdmin(PeriodicTask, self.site)
        self.request = self.patch_request(self.request_factory.get('/'))
        ma.run_tasks(self.request, PeriodicTask.objects.filter(id=self.m1.id))
        assert len(self.request._messages._queued_messages) == 1
        queued_message = self.request._messages._queued_messages[0].message
        assert queued_message == '1 task was successfully run'

    # don't hang if broker is down
    # https://github.com/celery/celery/issues/4627
    @pytest.mark.timeout(5)
    def test_run_tasks(self):
        ma = PeriodicTaskAdmin(PeriodicTask, self.site)
        self.request = self.patch_request(self.request_factory.get('/'))
        ma.run_tasks(self.request, PeriodicTask.objects.all())
        assert len(self.request._messages._queued_messages) == 1
        queued_message = self.request._messages._queued_messages[0].message
        assert queued_message == '2 tasks were successfully run'

    @pytest.mark.timeout(5)
    def test_run_task_headers(self, monkeypatch):
        def mock_apply_async(*args, **kwargs):
            self.captured_headers = kwargs.get('headers', {})

        monkeypatch.setattr('celery.app.task.Task.apply_async',
                            mock_apply_async)
        ma = PeriodicTaskAdmin(PeriodicTask, self.site)
        self.request = self.patch_request(self.request_factory.get('/'))
        ma.run_tasks(self.request, PeriodicTask.objects.filter(id=self.m1.id))
        assert 'periodic_task_name' in self.captured_headers
        assert self.captured_headers['periodic_task_name'] == self.m1.name
