import datetime
import os

try:
    from zoneinfo import ZoneInfo, available_timezones
except ImportError:
    from backports.zoneinfo import available_timezones, ZoneInfo

import pytest
from celery import schedules
from django.apps import apps
from django.conf import settings
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState
from django.test import TestCase, override_settings
from django.utils import timezone

from django_celery_beat import migrations as beat_migrations
from django_celery_beat.models import (DAYS, ClockedSchedule, CrontabSchedule,
                                       IntervalSchedule, PeriodicTasks,
                                       SolarSchedule,
                                       crontab_schedule_celery_timezone)
from t.proj.models import O2OToPeriodicTasks


class MigrationTests(TestCase):
    def test_no_future_duplicate_migration_numbers(self):
        """Verify no duplicate migration numbers.

        Migration files with the same number can cause issues with
        backward migrations, so avoid them.
        """
        path = os.path.dirname(beat_migrations.__file__)
        files = [f[:4] for f in os.listdir(path) if f.endswith('.py')]
        expected_duplicates = [
            (3, '0006'),
        ]
        duplicates_extra = sum(count - 1 for count, _ in expected_duplicates)
        duplicates_numbers = [number for _, number in expected_duplicates]
        self.assertEqual(
            len(files), len(set(files)) + duplicates_extra,
            msg=('Detected migration files with the same migration number'
                 ' (besides {})'.format(' and '.join(duplicates_numbers))))

    def test_models_match_migrations(self):
        """Make sure that no model changes exist.

        This logic is taken from django's makemigrations.py file.
        Here just detect if model changes exist that require
        a migration, and if so we fail.
        """
        app_labels = ['django_celery_beat']
        loader = MigrationLoader(None, ignore_no_migrations=True)
        questioner = NonInteractiveMigrationQuestioner(
            specified_apps=app_labels, dry_run=False)
        autodetector = MigrationAutodetector(
            loader.project_state(),
            ProjectState.from_apps(apps),
            questioner,
        )
        changes = autodetector.changes(
            graph=loader.graph,
            trim_to_apps=app_labels,
            convert_apps=app_labels,
            migration_name='fake_name',
        )
        self.assertTrue(
            not changes,
            msg='Model changes exist that do not have a migration')


class TestDuplicatesMixin:
    def _test_duplicate_schedules(self, cls, kwargs, schedule=None):
        sched1 = cls.objects.create(**kwargs)
        cls.objects.create(**kwargs)
        self.assertEqual(cls.objects.filter(**kwargs).count(), 2)
        # try to create a duplicate schedule from a celery schedule
        if schedule is None:
            schedule = sched1.schedule
        sched3 = cls.from_schedule(schedule)
        # the schedule should be the first of the 2 previous duplicates
        self.assertEqual(sched3, sched1)
        # and the duplicates should not be deleted !
        self.assertEqual(cls.objects.filter(**kwargs).count(), 2)


class CrontabScheduleTestCase(TestCase, TestDuplicatesMixin):
    FIRST_VALID_TIMEZONE = available_timezones().pop()

    def test_default_timezone_without_settings_config(self):
        assert crontab_schedule_celery_timezone() == "UTC"

    @override_settings(CELERY_TIMEZONE=FIRST_VALID_TIMEZONE)
    def test_default_timezone_with_settings_config(self):
        assert crontab_schedule_celery_timezone() == self.FIRST_VALID_TIMEZONE

    def test_duplicate_schedules(self):
        # See: https://github.com/celery/django-celery-beat/issues/322
        kwargs = {
            "minute": "*",
            "hour": "4",
            "day_of_week": "*",
            "day_of_month": "*",
            "month_of_year": "*",
            "day_of_week": "*",
        }
        schedule = schedules.crontab(hour="4")
        self._test_duplicate_schedules(CrontabSchedule, kwargs, schedule)


class SolarScheduleTestCase(TestCase):
    EVENT_CHOICES = SolarSchedule._meta.get_field("event").choices

    def test_celery_solar_schedules_sorted(self):
        assert all(
            self.EVENT_CHOICES[i] <= self.EVENT_CHOICES[i + 1]
            for i in range(len(self.EVENT_CHOICES) - 1)
        ), "SolarSchedule event choices are unsorted"

    def test_celery_solar_schedules_included_as_event_choices(self):
        """Make sure that all Celery solar schedules are included
        in SolarSchedule `event` field choices, keeping synchronized
        Celery solar events with `django-celery-beat` supported solar
        events.

        This test is necessary because Celery solar schedules are
        hardcoded at models so that Django can discover their translations.
        """
        event_choices_values = [value for value, tr in self.EVENT_CHOICES]
        for solar_event in schedules.solar._all_events:
            assert solar_event in event_choices_values

        for event_choice in event_choices_values:
            assert event_choice in schedules.solar._all_events


class IntervalScheduleTestCase(TestCase, TestDuplicatesMixin):

    def test_duplicate_schedules(self):
        kwargs = {'every': 1, 'period': IntervalSchedule.SECONDS}
        schedule = schedules.schedule(run_every=1.0)
        self._test_duplicate_schedules(IntervalSchedule, kwargs, schedule)


class ClockedScheduleTestCase(TestCase, TestDuplicatesMixin):

    def test_duplicate_schedules(self):
        kwargs = {'clocked_time': timezone.now()}
        self._test_duplicate_schedules(ClockedSchedule, kwargs)

    # IMPORTANT: we must have a valid timezone (not UTC) for accurate testing
    @override_settings(TIME_ZONE='Africa/Cairo')
    def test_timezone_format(self):
        """Ensure scheduled time is not shown in UTC when timezone is used"""
        tz_info = datetime.datetime.now(ZoneInfo(settings.TIME_ZONE))
        schedule, created = ClockedSchedule.objects.get_or_create(
            clocked_time=tz_info)
        # testnig str(schedule) calls make_aware() internally
        assert str(schedule.clocked_time) == str(schedule)


@pytest.mark.django_db()
class OneToOneRelTestCase(TestCase):
    """
    Make sure that when OneToOne relation Model changed,
    the `PeriodicTasks.last_update` will be update.
    """

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.interval_schedule = IntervalSchedule.objects.create(
            every=10, period=DAYS
        )

    def test_trigger_update_when_saved(self):
        o2o_to_periodic_tasks = O2OToPeriodicTasks.objects.create(
            name='name1',
            task='task1',
            enabled=True,
            interval=self.interval_schedule
        )
        not_changed_dt = PeriodicTasks.last_change()
        o2o_to_periodic_tasks.enabled = True  # Change something on instance.
        o2o_to_periodic_tasks.save()
        has_changed_dt = PeriodicTasks.last_change()
        self.assertTrue(
            not_changed_dt != has_changed_dt,
            'The `PeriodicTasks.last_update` has not be update.'
        )
        # Check the `PeriodicTasks` does be updated.

    def test_trigger_update_when_deleted(self):
        o2o_to_periodic_tasks = O2OToPeriodicTasks.objects.create(
            name='name1',
            task='task1',
            enabled=True,
            interval=self.interval_schedule
        )
        not_changed_dt = PeriodicTasks.last_change()
        o2o_to_periodic_tasks.delete()
        has_changed_dt = PeriodicTasks.last_change()
        self.assertTrue(
            not_changed_dt != has_changed_dt,
            'The `PeriodicTasks.last_update` has not be update.'
        )
        # Check the `PeriodicTasks` does be updated.


class HumanReadableTestCase(TestCase):
    def test_good(self):
        """Valid crontab display."""
        cron = CrontabSchedule.objects.create(
            hour="2",
            minute="0",
            day_of_week="mon",
        )
        self.assertNotEqual(
            cron.human_readable, "0 2 * * mon UTC"
        )

    def test_invalid(self):
        """Invalid crontab display."""
        cron = CrontabSchedule.objects.create(
            hour="2",
            minute="0",
            day_of_week="monxxx",
        )
        self.assertEqual(
            cron.human_readable, "0 2 * * monxxx UTC"
        )

    def test_long_name(self):
        """Long day name display."""
        # TODO: this should eventually work, but probably needs conversion
        # before passing data to cron_description
        cron = CrontabSchedule.objects.create(
            hour="2",
            minute="0",
            day_of_week="monday",
        )
        self.assertEqual(
            cron.human_readable, "0 2 * * monday UTC"
        )
