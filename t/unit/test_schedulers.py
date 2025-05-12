import math
import os
import time
from datetime import datetime, timedelta
from itertools import count
from time import monotonic
from unittest.mock import patch

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python 3.8

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
        m = self.create_model_interval(
            schedule(timedelta(seconds=interval)),
            start_time=right_now,
            last_run_at=one_interval_ago
        )
        e = self.Entry(m, app=self.app)
        isdue, delay = e.is_due()
        assert isdue
        assert delay == interval

        tomorrow = right_now + timedelta(days=1)
        m2 = self.create_model_interval(
            schedule(timedelta(seconds=interval)),
            start_time=tomorrow,
            last_run_at=one_interval_ago
        )
        e2 = self.Entry(m2, app=self.app)
        isdue, delay = e2.is_due()
        assert not isdue
        assert delay == math.ceil(
            (tomorrow - right_now).total_seconds()
        )

    def test_one_off_task(self):
        interval = 10
        right_now = self.app.now()
        one_interval_ago = right_now - timedelta(seconds=interval)
        m = self.create_model_interval(
            schedule(timedelta(seconds=interval)),
            one_off=True,
            last_run_at=one_interval_ago,
            total_run_count=0
        )
        e = self.Entry(m, app=self.app)
        isdue, delay = e.is_due()
        assert isdue
        assert delay == interval

        m2 = self.create_model_interval(
            schedule(timedelta(seconds=interval)),
            one_off=True,
            last_run_at=one_interval_ago,
            total_run_count=1
        )
        e2 = self.Entry(m2, app=self.app)
        isdue, delay = e2.is_due()
        assert not isdue
        assert delay == NEVER_CHECK_TIMEOUT

    def test_task_with_expires(self):
        interval = 10
        right_now = self.app.now()
        one_second_later = right_now + timedelta(seconds=1)
        m = self.create_model_interval(
            schedule(timedelta(seconds=interval)),
            start_time=right_now,
            expires=one_second_later
        )
        e = self.Entry(m, app=self.app)
        isdue, delay = e.is_due()
        assert isdue
        assert delay == interval

        m2 = self.create_model_interval(
            schedule(timedelta(seconds=interval)),
            start_time=right_now,
            expires=right_now
        )
        e2 = self.Entry(m2, app=self.app)
        isdue, delay = e2.is_due()
        assert not isdue
        assert delay == NEVER_CHECK_TIMEOUT

        one_second_ago = right_now - timedelta(seconds=1)
        m2 = self.create_model_interval(
            schedule(timedelta(seconds=interval)),
            start_time=right_now,
            expires=one_second_ago
        )
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
            crontab(hour=str((now_hour + 3) % 24)))
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

        # Check for presence of standard tasks
        expected_task_names = {
            self.m1.name,  # interval task
            self.m2.name,  # interval task
            self.m3.name,  # crontab task
            self.m4.name,  # solar task
            self.m6.name,  # clocked task (near future)
            self.m8.name,  # crontab task (current hour)
            self.m9.name,  # crontab task (current hour + 1)
            self.m10.name,  # crontab task (current hour - 1)
            'celery.backend_cleanup'  # auto-added by system
        }

        # The distant future crontab task (hour + 3) should be excluded
        distant_task_name = self.m11.name

        # But if it's hour is 4 (or converts to 4 after timezone adjustment),
        # it would be included because of the special handling for hour=4
        current_hour = timezone.localtime(timezone.now()).hour
        is_hour_four_task = False

        # Check if the task would have hour 4.
        if self.m11.crontab.hour == '4' or (current_hour + 3) % 24 == 4:
            is_hour_four_task = True

        # Add to expected tasks if it's an hour=4 task
        if is_hour_four_task:
            expected_task_names.add(distant_task_name)

        # Verify all expected tasks are present in the schedule
        schedule_task_names = set(sched.keys())
        assert schedule_task_names == expected_task_names, (
            f"Task mismatch. Expected: {expected_task_names}, "
            f"Got: {schedule_task_names}"
        )

        # Verify all entries are the right type
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
        assert not self.s.schedules_equal(
            self.s.schedule, self.s.schedule
        )

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

    def test_crontab_with_start_time_between_now_and_crontab(self, app):
        now = app.now()
        delay_minutes = 2

        test_start_time = now + timedelta(minutes=delay_minutes)

        crontab_time = test_start_time + timedelta(minutes=delay_minutes)

        task = self.create_model_crontab(
            crontab(minute=f'{crontab_time.minute}'),
            start_time=test_start_time)

        entry = EntryTrackSave(task, app=app)

        is_due, next_check = entry.is_due()

        expected_delay = 2 * delay_minutes * 60

        assert not is_due
        assert next_check == pytest.approx(expected_delay, abs=60)

    def test_crontab_with_start_time_after_crontab(self, app):
        now = app.now()

        delay_minutes = 2

        crontab_time = now + timedelta(minutes=delay_minutes)

        test_start_time = crontab_time + timedelta(minutes=delay_minutes)

        task = self.create_model_crontab(
            crontab(minute=f'{crontab_time.minute}'),
            start_time=test_start_time)

        entry = EntryTrackSave(task, app=app)

        is_due, next_check = entry.is_due()

        expected_delay = delay_minutes * 60 + 3600

        assert not is_due
        assert next_check == pytest.approx(expected_delay, abs=60)

    def test_crontab_with_start_time_different_time_zone(self, app):
        now = app.now()

        delay_minutes = 2

        test_start_time = now + timedelta(minutes=delay_minutes)

        crontab_time = test_start_time + timedelta(minutes=delay_minutes)

        tz = ZoneInfo('Asia/Shanghai')
        test_start_time = test_start_time.astimezone(tz)

        task = self.create_model_crontab(
            crontab(minute=f'{crontab_time.minute}'),
            start_time=test_start_time)

        entry = EntryTrackSave(task, app=app)

        is_due, next_check = entry.is_due()

        expected_delay = 2 * delay_minutes * 60

        assert not is_due
        assert next_check == pytest.approx(expected_delay, abs=60)

        now = app.now()

        crontab_time = now + timedelta(minutes=delay_minutes)

        test_start_time = crontab_time + timedelta(minutes=delay_minutes)

        tz = ZoneInfo('Asia/Shanghai')
        test_start_time = test_start_time.astimezone(tz)

        task = self.create_model_crontab(
            crontab(minute=f'{crontab_time.minute}'),
            start_time=test_start_time)

        entry = EntryTrackSave(task, app=app)

        is_due, next_check = entry.is_due()

        expected_delay = delay_minutes * 60 + 3600

        assert not is_due
        assert next_check == pytest.approx(expected_delay, abs=60)

    def test_crontab_with_start_time_tick(self, app):
        PeriodicTask.objects.all().delete()
        s = self.Scheduler(app=self.app)
        assert not s._heap

        m1 = self.create_model_interval(schedule(timedelta(seconds=3)))
        m1.save()

        now = timezone.now()
        start_time = now + timedelta(minutes=1)
        crontab_trigger_time = now + timedelta(minutes=2)

        m2 = self.create_model_crontab(
            crontab(minute=f'{crontab_trigger_time.minute}'),
            start_time=start_time)
        m2.save()

        e2 = EntryTrackSave(m2, app=self.app)
        is_due, _ = e2.is_due()

        max_iterations = 1000
        iterations = 0
        while (not is_due and iterations < max_iterations):
            s.tick()
            assert s._heap[0][2].name != m2.name
            is_due, _ = e2.is_due()

    @pytest.mark.django_db
    def test_crontab_exclusion_logic_basic(self):
        current_hour = datetime.now().hour
        cron_current_hour = CrontabSchedule.objects.create(
            hour=str(current_hour)
        )
        cron_plus_one = CrontabSchedule.objects.create(
            hour=str((current_hour + 1) % 24)
        )
        cron_plus_two = CrontabSchedule.objects.create(
            hour=str((current_hour + 2) % 24)
        )
        cron_minus_one = CrontabSchedule.objects.create(
            hour=str((current_hour - 1) % 24)
        )
        cron_minus_two = CrontabSchedule.objects.create(
            hour=str((current_hour - 2) % 24)
        )
        cron_outside = CrontabSchedule.objects.create(
            hour=str((current_hour + 5) % 24)
        )

        # Create a special hour 4 schedule that should always be included
        cron_hour_four = CrontabSchedule.objects.create(hour='4')

        # Create periodic tasks using these schedules
        task_current = self.create_model(
            name='task-current',
            crontab=cron_current_hour
        )
        task_current.save()

        task_plus_one = self.create_model(
            name='task-plus-one',
            crontab=cron_plus_one
        )
        task_plus_one.save()

        task_plus_two = self.create_model(
            name='task-plus-two',
            crontab=cron_plus_two
        )
        task_plus_two.save()

        task_minus_one = self.create_model(
            name='task-minus-one',
            crontab=cron_minus_one
        )
        task_minus_one.save()

        task_minus_two = self.create_model(
            name='task-minus-two',
            crontab=cron_minus_two
        )
        task_minus_two.save()

        task_outside = self.create_model(
            name='task-outside',
            crontab=cron_outside
        )
        task_outside.save()

        task_hour_four = self.create_model(
            name='task-hour-four',
            crontab=cron_hour_four
        )
        task_hour_four.save()

        # Run the scheduler's exclusion logic
        exclude_query = self.s._get_crontab_exclude_query()

        # Get excluded task IDs
        excluded_tasks = set(
            PeriodicTask.objects.filter(exclude_query).values_list(
                'id', flat=True
            )
        )

        # The test that matters is that hour 4 is always included
        assert task_hour_four.id not in excluded_tasks

        # Assert that tasks within the time window are not excluded
        for task_id in [task_current.id, task_plus_one.id, task_plus_two.id,
                        task_minus_one.id, task_minus_two.id]:
            assert task_id not in excluded_tasks

        if task_outside.crontab.hour != '4':
            assert task_outside.id in excluded_tasks

    @pytest.mark.django_db
    def test_crontab_special_hour_four(self):
        """
        Test that schedules with hour=4 are always included, regardless of
        the current time.
        """
        # Create a task with hour=4
        cron_hour_four = CrontabSchedule.objects.create(hour='4')
        task_hour_four = self.create_model(
            name='special-cleanup-task',
            crontab=cron_hour_four
        )

        # Run the scheduler's exclusion logic
        exclude_query = self.s._get_crontab_exclude_query()

        # Get excluded task IDs
        excluded_tasks = set(
            PeriodicTask.objects.filter(exclude_query).values_list(
                'id', flat=True
            )
        )

        # The hour=4 task should never be excluded
        assert task_hour_four.id not in excluded_tasks

    @pytest.mark.django_db
    @patch('django_celery_beat.schedulers.aware_now')
    @patch('django.utils.timezone.get_current_timezone')
    def test_crontab_timezone_conversion(self, mock_get_tz, mock_aware_now):
        # Set up mocks for server timezone and current time
        from datetime import datetime
        server_tz = ZoneInfo("Asia/Tokyo")

        mock_get_tz.return_value = server_tz

        # Server time is 17:00 Tokyo time
        mock_now_dt = datetime(2023, 1, 1, 17, 0, 0, tzinfo=server_tz)
        mock_aware_now.return_value = mock_now_dt

        # Create tasks with the following crontab schedules:
        # 1. UTC task at hour 8 - equivalent to 17:00 Tokyo time (current hour)
        #    - should be included
        # 2. New York task at hour 3 - equivalent to 17:00 Tokyo time
        #    (current hour) - should be included
        # 3. UTC task at hour 3 - equivalent to 12:00 Tokyo time
        #    - should be excluded (outside window)

        # Create crontab schedules in different timezones
        utc_current_hour = CrontabSchedule.objects.create(
            hour='8', timezone='UTC'
        )
        ny_current_hour = CrontabSchedule.objects.create(
            hour='3', timezone='America/New_York'
        )
        utc_outside_window = CrontabSchedule.objects.create(
            hour='3', timezone='UTC'
        )

        # Create periodic tasks using these schedules
        task_utc_current = self.create_model(
            name='utc-current-hour',
            crontab=utc_current_hour
        )
        task_utc_current.save()

        task_ny_current = self.create_model(
            name='ny-current-hour',
            crontab=ny_current_hour
        )
        task_ny_current.save()

        task_utc_outside = self.create_model(
            name='utc-outside-window',
            crontab=utc_outside_window
        )
        task_utc_outside.save()

        # Run the scheduler's exclusion logic
        exclude_query = self.s._get_crontab_exclude_query()

        # Get excluded task IDs
        excluded_tasks = set(
            PeriodicTask.objects.filter(exclude_query).values_list(
                'id', flat=True
            )
        )

        # Current hour tasks in different timezones should not be excluded
        assert task_utc_current.id not in excluded_tasks, (
            "UTC current hour task should be included"
        )
        assert task_ny_current.id not in excluded_tasks, (
            "New York current hour task should be included"
        )

        # Task outside window should be excluded
        assert task_utc_outside.id in excluded_tasks, (
            "UTC outside window task should be excluded"
        )

    @pytest.mark.django_db
    @patch('django.utils.timezone.get_current_timezone')
    @patch('django_celery_beat.schedulers.aware_now')
    def test_crontab_timezone_conversion_with_negative_offset_and_dst(
        self, mock_aware_now, mock_get_tz
    ):
        # Set up mocks for server timezone and current time
        from datetime import datetime

        server_tz = ZoneInfo("UTC")

        mock_get_tz.return_value = server_tz

        # Server time is 17:00 UTC in June
        mock_now_dt = datetime(2023, 6, 1, 17, 0, 0, tzinfo=server_tz)
        mock_aware_now.return_value = mock_now_dt

        # Create tasks with the following crontab schedules:
        # 1. Asia/Tokyo task at hour 2 - equivalent to 17:00 UTC (current hour)
        #    - should be included
        # 2. Europe/Paris task at hour 19 - equivalent to 17:00 UTC
        #    (current hour) - should be included
        # 3. Europe/Paris task at hour 15 - equivalent to 13:00 UTC
        #    - should be excluded (outside window)

        # Create crontab schedules in different timezones
        tokyo_current_hour = CrontabSchedule.objects.create(
            hour='2', timezone='Asia/Tokyo'
        )
        paris_current_hour = CrontabSchedule.objects.create(
            hour='19', timezone='Europe/Paris'
        )
        paris_outside_window = CrontabSchedule.objects.create(
            hour='14', timezone='Europe/Paris'
        )

        # Create periodic tasks using these schedules
        task_utc_current = self.create_model(
            name='tokyo-current-hour',
            crontab=tokyo_current_hour
        )
        task_utc_current.save()

        task_ny_current = self.create_model(
            name='paros-current-hour',
            crontab=paris_current_hour
        )
        task_ny_current.save()

        task_utc_outside = self.create_model(
            name='paris-outside-window',
            crontab=paris_outside_window
        )
        task_utc_outside.save()

        # Run the scheduler's exclusion logic
        exclude_query = self.s._get_crontab_exclude_query()

        # Get excluded task IDs
        excluded_tasks = set(
            PeriodicTask.objects.filter(exclude_query).values_list(
                'id', flat=True
            )
        )

        # Current hour tasks in different timezones should not be excluded
        assert task_utc_current.id not in excluded_tasks, (
            "Tokyo current hour task should be included"
        )
        assert task_ny_current.id not in excluded_tasks, (
            "Paris current hour task should be included"
        )

        # Task outside window should be excluded
        assert task_utc_outside.id in excluded_tasks, (
            "Paris outside window task should be excluded"
        )


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
        due_datetime = make_aware(datetime(
            day=26,
            month=7,
            year=3000,
            hour=1,
            minute=0
        ))  # future time
        s = ClockedSchedule(clocked_time=due_datetime)
        dt = datetime(day=25, month=7, year=2050, hour=1, minute=0)
        dt_lastrun = make_aware(dt)

        assert s.schedule is not None
        isdue, nextcheck = s.schedule.is_due(dt_lastrun)
        # False means task isn't due, but keep checking.
        assert isdue is False
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


@pytest.mark.django_db
class test_timezone_offset_handling:
    def setup_method(self):
        self.app = patch("django_celery_beat.schedulers.current_app").start()

    def teardown_method(self):
        patch.stopall()

    @patch("django_celery_beat.schedulers.aware_now")
    def test_server_timezone_handling_with_zoneinfo(self, mock_aware_now):
        """Test handling when server timezone is already a ZoneInfo instance."""

        # Create a mock scheduler with only the methods we need to test
        class MockScheduler:
            _get_timezone_offset = schedulers.DatabaseScheduler._get_timezone_offset

        s = MockScheduler()

        tokyo_tz = ZoneInfo("Asia/Tokyo")
        mock_now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=tokyo_tz)
        mock_aware_now.return_value = mock_now

        # Test with a different timezone
        new_york_tz = "America/New_York"
        offset = s._get_timezone_offset(new_york_tz)  # Pass self explicitly

        # Tokyo is UTC+9, New York is UTC-5, so difference should be 14 hours
        assert offset == 14
        assert mock_aware_now.called

    @patch("django_celery_beat.schedulers.aware_now")
    def test_timezone_offset_with_zoneinfo_object_param(self, mock_aware_now):
        """Test handling when timezone_name parameter is a ZoneInfo object."""

        class MockScheduler:
            _get_timezone_offset = schedulers.DatabaseScheduler._get_timezone_offset

        s = MockScheduler()

        tokyo_tz = ZoneInfo("Asia/Tokyo")
        mock_now = datetime(2023, 1, 1, 12, 0, 0, tzinfo=tokyo_tz)
        mock_aware_now.return_value = mock_now

        # Test with a ZoneInfo object as parameter
        new_york_tz = ZoneInfo("America/New_York")
        offset = s._get_timezone_offset(new_york_tz)  # Pass self explicitly

        # Tokyo is UTC+9, New York is UTC-5, so difference should be 14 hours
        assert offset == 14
