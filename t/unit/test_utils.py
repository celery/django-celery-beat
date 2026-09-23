from datetime import date, datetime, timedelta
from datetime import timezone as datetime_timezone
from unittest.mock import patch

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo

import pytest
from django.db.models.functions import Now
from django.test import TestCase, override_settings
from django.utils import timezone

from django_celery_beat.models import ClockedSchedule, PeriodicTasks
from django_celery_beat.utils import (aware_now, clocked_due_after_next_sync,
                                      next_schedule_sync_at)


@pytest.mark.django_db
class TestUtils(TestCase):
    def test_aware_now_with_use_tz_true(self):
        """Test aware_now when USE_TZ is True"""
        with override_settings(USE_TZ=True):
            result = aware_now()
            assert timezone.is_aware(result)
            # Convert both timezones to string for comparison
            assert str(result.tzinfo) == str(timezone.get_current_timezone())

    def test_aware_now_with_use_tz_false(self):
        """Test aware_now when USE_TZ is False"""
        with override_settings(USE_TZ=False, TIME_ZONE="Asia/Tokyo"):
            result = aware_now()
            assert timezone.is_aware(result)
            assert result.tzinfo.key == "Asia/Tokyo"

    def test_aware_now_with_use_tz_false_default_timezone(self):
        """Test aware_now when USE_TZ is False and default TIME_ZONE"""
        with override_settings(USE_TZ=False):  # Let Django use its default UTC
            result = aware_now()
            assert timezone.is_aware(result)
            assert str(result.tzinfo) == "UTC"

    @override_settings(USE_TZ=False)
    def test_aware_clocked_use_tz_false(self):
        assert clocked_due_after_next_sync(aware_now() + timedelta(days=1))
        assert not clocked_due_after_next_sync(aware_now())

    def test_far_future_clocked_string_skips_change(self):
        PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        ClockedSchedule.objects.create(clocked_time='2130-01-02T00:00:00Z')
        assert PeriodicTasks.last_change() == before

    def test_near_clocked_string_tracks_change(self):
        PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        clocked_time = (timezone.now() + timedelta(minutes=1)).isoformat()
        ClockedSchedule.objects.create(clocked_time=clocked_time)
        assert PeriodicTasks.last_change() > before

    def test_near_clocked_database_expression_tracks_change(self):
        PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        ClockedSchedule.objects.create(clocked_time=Now() + timedelta(minutes=1))
        assert PeriodicTasks.last_change() > before

    def test_far_future_clocked_database_expression_skips_change(self):
        PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        ClockedSchedule.objects.create(clocked_time=Now() + timedelta(minutes=10))
        assert PeriodicTasks.last_change() == before

    def test_far_future_clocked_date_string_skips_change(self):
        PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        with pytest.warns(RuntimeWarning):
            ClockedSchedule.objects.create(clocked_time='2130-01-02')
        assert PeriodicTasks.last_change() == before

    def test_near_clocked_date_string_tracks_change(self):
        current = datetime(2026, 1, 1, 23, 59, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now',
                   return_value=current - timedelta(seconds=1)):
            PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        with patch('django.utils.timezone.now', return_value=current), \
                pytest.warns(RuntimeWarning):
            ClockedSchedule.objects.create(clocked_time='2026-01-02')
        assert PeriodicTasks.last_change() > before

    def test_far_future_clocked_date_object_skips_change(self):
        PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        with pytest.warns(RuntimeWarning):
            ClockedSchedule.objects.create(clocked_time=date(2130, 1, 2))
        assert PeriodicTasks.last_change() == before

    def test_near_clocked_date_object_tracks_change(self):
        current = datetime(2026, 1, 1, 23, 59, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now',
                   return_value=current - timedelta(seconds=1)):
            PeriodicTasks.update_changed()
        before = PeriodicTasks.last_change()
        with patch('django.utils.timezone.now', return_value=current), \
                pytest.warns(RuntimeWarning):
            ClockedSchedule.objects.create(clocked_time=date(2026, 1, 2))
        assert PeriodicTasks.last_change() > before

    def test_skip_change_only_when_beat_can_sync_before_clocked_task(self):
        current = datetime(2026, 1, 1, tzinfo=datetime_timezone.utc)
        # The full sync is due in 300 seconds; beat may wake up 5 seconds later.
        with patch('django.utils.timezone.now', return_value=current):
            assert not clocked_due_after_next_sync(current + timedelta(seconds=305))
            assert clocked_due_after_next_sync(current + timedelta(seconds=306))

    @override_settings(USE_TZ=True, TIME_ZONE='America/New_York')
    def test_clocked_cutoff_across_dst_start(self):
        current = datetime(2026, 3, 8, 6, 59, tzinfo=datetime_timezone.utc)
        due = datetime(2026, 3, 8, 3, tzinfo=ZoneInfo('America/New_York'))
        with patch('django.utils.timezone.now', return_value=current):
            assert not clocked_due_after_next_sync(due)
            assert not clocked_due_after_next_sync(
                due.astimezone(datetime_timezone.utc),
            )

    @override_settings(USE_TZ=True, TIME_ZONE='America/New_York')
    def test_clocked_cutoff_across_dst_end(self):
        current = datetime(2026, 11, 1, 5, 59, tzinfo=datetime_timezone.utc)
        due = datetime(
            2026, 11, 1, 1, 10, fold=1, tzinfo=ZoneInfo('America/New_York'),
        )
        with patch('django.utils.timezone.now', return_value=current):
            assert clocked_due_after_next_sync(due)
            assert clocked_due_after_next_sync(
                due.astimezone(datetime_timezone.utc),
            )

    @override_settings(USE_TZ=True, TIME_ZONE='America/New_York')
    def test_sync_cutoff_across_dst_end_uses_elapsed_time(self):
        current = datetime(2026, 11, 1, 5, 59, tzinfo=datetime_timezone.utc)
        with patch('django.utils.timezone.now', return_value=current):
            assert next_schedule_sync_at() == datetime(
                2026, 11, 1, 6, 4, tzinfo=datetime_timezone.utc,
            )

    @override_settings(USE_TZ=False, TIME_ZONE='Asia/Tokyo')
    def test_naive_clocked_time_and_sync_cutoff_without_tz(self):
        current = datetime(2030, 1, 2)
        with patch('django.utils.timezone.now', return_value=current):
            assert next_schedule_sync_at() == datetime(2030, 1, 2, 0, 5)
            assert not clocked_due_after_next_sync(datetime(2030, 1, 2, 0, 4))
            assert clocked_due_after_next_sync(datetime(2030, 1, 2, 0, 6))

    @override_settings(USE_TZ=False, TIME_ZONE='America/New_York')
    def test_aware_clocked_time_across_dst_start_without_tz(self):
        current = datetime(2026, 3, 8, 1, 59, tzinfo=ZoneInfo('America/New_York'))
        due = datetime(2026, 3, 8, 3, tzinfo=ZoneInfo('America/New_York'))
        with patch('django_celery_beat.utils.aware_now', return_value=current):
            assert not clocked_due_after_next_sync(due)
