import pytest
from django.test import TestCase, override_settings
from django.utils import timezone

from django_celery_beat.utils import aware_now


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
