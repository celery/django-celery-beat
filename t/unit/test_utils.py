from unittest import mock
from django.test import TestCase
from datetime import datetime
import time

from django_celery_beat import utils
from django.utils import timezone

class UtilsTest(TestCase):

    @mock.patch('django_celery_beat.utils.timezone.localtime')
    @mock.patch('django_celery_beat.utils.timezone.get_default_timezone')
    @mock.patch('django_celery_beat.utils.timezone.make_aware')
    @mock.patch('django_celery_beat.utils.time.localtime')
    @mock.patch('django_celery_beat.utils.timezone.is_naive')
    @mock.patch('django_celery_beat.utils.getattr')
    def test_make_aware_use_tz_naive(self, mock_getattr, mock_is_naive, mock_localtime_1, mock_make_aware, mock_get_default_timezone, mock_localtime_2):
        dt = datetime(2022, 11, 6, 1, 15, 0)
        mock_getattr.return_value = True
        mock_is_naive.return_value = True
        mock_get_default_timezone.return_value = "America/Los_Angeles"
        mock_localtime_2.return_value = time.struct_time([2022, 11, 6, 1, 15, 0, 0, 310, 0])
        mock_make_aware.return_value = dt

        self.assertEquals(utils.make_aware(dt), mock_localtime_2.return_value)

        mock_localtime_1.assert_not_called()
        mock_make_aware.assert_called_with(dt, timezone.utc)
        mock_get_default_timezone.assert_called()
        mock_localtime_2.assert_called_with(dt, "America/Los_Angeles")

    @mock.patch('django_celery_beat.utils.timezone.localtime')
    @mock.patch('django_celery_beat.utils.timezone.get_default_timezone')
    @mock.patch('django_celery_beat.utils.timezone.make_aware')
    @mock.patch('django_celery_beat.utils.time.localtime')
    @mock.patch('django_celery_beat.utils.timezone.is_naive')
    @mock.patch('django_celery_beat.utils.getattr')
    def test_make_aware_use_tz_not_naive(self, mock_getattr, mock_is_naive, mock_localtime_1, mock_make_aware, mock_get_default_timezone, mock_localtime_2):
        dt = datetime(2022, 11, 6, 1, 15, 0)
        mock_getattr.return_value = True
        mock_is_naive.return_value = False
        mock_get_default_timezone.return_value = "America/Los_Angeles"
        mock_localtime_2.return_value = time.struct_time([2022, 11, 6, 1, 15, 0, 0, 310, 0])
        mock_make_aware.return_value = dt

        self.assertEquals(utils.make_aware(dt), mock_localtime_2.return_value)

        mock_localtime_1.assert_not_called()
        mock_make_aware.assert_not_called()
        mock_get_default_timezone.assert_called()
        mock_localtime_2.assert_called_with(dt, "America/Los_Angeles")

    @mock.patch('django_celery_beat.utils.timezone.localtime')
    @mock.patch('django_celery_beat.utils.timezone.get_default_timezone')
    @mock.patch('django_celery_beat.utils.timezone.make_aware')
    @mock.patch('django_celery_beat.utils.time.localtime')
    @mock.patch('django_celery_beat.utils.timezone.is_naive')
    @mock.patch('django_celery_beat.utils.getattr')
    def test_make_aware_not_use_tz_naive_dst(self, mock_getattr, mock_is_naive, mock_localtime_1, mock_make_aware, mock_get_default_timezone, mock_localtime_2):
        dt = datetime(2022, 11, 6, 1, 15, 0)
        mock_getattr.return_value = False
        mock_is_naive.return_value = True
        mock_get_default_timezone.return_value = "America/Los_Angeles"
        mock_localtime_1.return_value = time.struct_time([2022, 11, 6, 1, 15, 0, 0, 310, 1])
        mock_make_aware.return_value = dt

        self.assertEquals(utils.make_aware(dt), dt)

        mock_localtime_1.assert_called_with()
        mock_make_aware.assert_called_with(dt, "America/Los_Angeles", is_dst=True)
        mock_get_default_timezone.assert_called()
        mock_localtime_2.assert_not_called()

    @mock.patch('django_celery_beat.utils.timezone.localtime')
    @mock.patch('django_celery_beat.utils.timezone.get_default_timezone')
    @mock.patch('django_celery_beat.utils.timezone.make_aware')
    @mock.patch('django_celery_beat.utils.time.localtime')
    @mock.patch('django_celery_beat.utils.timezone.is_naive')
    @mock.patch('django_celery_beat.utils.getattr')
    def test_make_aware_not_use_tz_naive_not_dst(self, mock_getattr, mock_is_naive, mock_localtime_1, mock_make_aware, mock_get_default_timezone, mock_localtime_2):
        dt = datetime(2022, 11, 6, 1, 15, 0)
        mock_getattr.return_value = False
        mock_is_naive.return_value = True
        mock_get_default_timezone.return_value = "America/Los_Angeles"
        mock_localtime_1.return_value = time.struct_time([2022, 11, 6, 1, 15, 0, 0, 310, 0])
        mock_make_aware.return_value = dt

        self.assertEquals(utils.make_aware(dt), dt)

        mock_localtime_1.assert_called_with()
        mock_make_aware.assert_called_with(dt, "America/Los_Angeles", is_dst=False)
        mock_get_default_timezone.assert_called()
        mock_localtime_2.assert_not_called()

    @mock.patch('django_celery_beat.utils.timezone.localtime')
    @mock.patch('django_celery_beat.utils.timezone.get_default_timezone')
    @mock.patch('django_celery_beat.utils.timezone.make_aware')
    @mock.patch('django_celery_beat.utils.time.localtime')
    @mock.patch('django_celery_beat.utils.timezone.is_naive')
    @mock.patch('django_celery_beat.utils.getattr')
    def test_make_aware_not_use_tz_not_naive_dst(self, mock_getattr, mock_is_naive, mock_localtime_1, mock_make_aware, mock_get_default_timezone, mock_localtime_2):
        dt = datetime(2022, 11, 6, 1, 15, 0)
        mock_getattr.return_value = False
        mock_is_naive.return_value = False
        mock_get_default_timezone.return_value = "America/Los_Angeles"
        mock_localtime_1.return_value = time.struct_time([2022, 11, 6, 1, 15, 0, 0, 310, 0])
        mock_make_aware.return_value = dt

        self.assertEquals(utils.make_aware(dt), dt)

        mock_localtime_1.assert_not_called()
        mock_make_aware.assert_not_called()
        mock_get_default_timezone.assert_not_called()
        mock_localtime_2.assert_not_called()
