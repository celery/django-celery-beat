from itertools import combinations
from unittest import mock

import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase

from django_celery_beat.admin import PeriodicTaskAdmin, PeriodicTaskForm
from django_celery_beat.models import (DAYS, ClockedSchedule, CrontabSchedule,
                                       IntervalSchedule, PeriodicTask,
                                       SolarSchedule)


@pytest.mark.django_db
class ActionsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.interval_schedule = IntervalSchedule.objects.create(every=10,
                                                                period=DAYS)

    def test_toggle_action(self):
        PeriodicTask.objects.create(name='name1', task='task1', enabled=False,
                                    interval=self.interval_schedule)
        PeriodicTask.objects.create(name='name2', task='task2', enabled=True,
                                    interval=self.interval_schedule)
        PeriodicTask.objects.create(name='name3', task='task3', enabled=False,
                                    interval=self.interval_schedule)

        qs = PeriodicTask.objects.all()
        PeriodicTaskAdmin(PeriodicTask, None)._toggle_tasks_activity(qs)

        e1 = PeriodicTask.objects.get(name='name1', task='task1').enabled
        e2 = PeriodicTask.objects.get(name='name2', task='task2').enabled
        e3 = PeriodicTask.objects.get(name='name3', task='task3').enabled
        self.assertTrue(e1)
        self.assertFalse(e2)
        self.assertTrue(e3)

    def test_toggle_action_all_enabled(self):
        PeriodicTask.objects.create(name='name1', task='task1', enabled=True,
                                    interval=self.interval_schedule)
        PeriodicTask.objects.create(name='name2', task='task2', enabled=True,
                                    interval=self.interval_schedule)
        PeriodicTask.objects.create(name='name3', task='task3', enabled=True,
                                    interval=self.interval_schedule)

        qs = PeriodicTask.objects.all()
        PeriodicTaskAdmin(PeriodicTask, None)._toggle_tasks_activity(qs)

        e1 = PeriodicTask.objects.get(name='name1', task='task1').enabled
        e2 = PeriodicTask.objects.get(name='name2', task='task2').enabled
        e3 = PeriodicTask.objects.get(name='name3', task='task3').enabled
        self.assertFalse(e1)
        self.assertFalse(e2)
        self.assertFalse(e3)

    def test_toggle_action_all_disabled(self):

        PeriodicTask.objects.create(name='name1', task='task1', enabled=False,
                                    interval=self.interval_schedule)
        PeriodicTask.objects.create(name='name2', task='task2', enabled=False,
                                    interval=self.interval_schedule)
        PeriodicTask.objects.create(name='name3', task='task3', enabled=False,
                                    interval=self.interval_schedule)

        qs = PeriodicTask.objects.all()
        PeriodicTaskAdmin(PeriodicTask, None)._toggle_tasks_activity(qs)

        e1 = PeriodicTask.objects.get(name='name1', task='task1').enabled
        e2 = PeriodicTask.objects.get(name='name2', task='task2').enabled
        e3 = PeriodicTask.objects.get(name='name3', task='task3').enabled
        self.assertTrue(e1)
        self.assertTrue(e2)
        self.assertTrue(e3)


@pytest.mark.django_db
class ValidateUniqueTests(TestCase):

    def test_validate_unique_raises_if_schedule_not_set(self):
        with self.assertRaises(ValidationError) as cm:
            PeriodicTask(name='task0').validate_unique()
        self.assertEqual(
            cm.exception.args[0],
            'One of clocked, interval, crontab, or solar must be set.',
        )

    def test_validate_unique_raises_for_multiple_schedules(self):
        schedules = [
            ('crontab', CrontabSchedule()),
            ('interval', IntervalSchedule()),
            ('solar', SolarSchedule()),
            ('clocked', ClockedSchedule())
        ]
        expected_error_msg = (
            'Only one of clocked, interval, crontab, or solar '
            'must be set'
        )
        for i, options in enumerate(combinations(schedules, 2)):
            name = f'task{i}'
            options_dict = dict(options)
            with self.assertRaises(ValidationError) as cm:
                PeriodicTask(name=name, **options_dict).validate_unique()
            errors = cm.exception.args[0]
            self.assertEqual(errors.keys(), options_dict.keys())
            for error_msg in errors.values():
                self.assertEqual(error_msg, [expected_error_msg])

    def test_validate_unique_not_raises(self):
        PeriodicTask(crontab=CrontabSchedule()).validate_unique()
        PeriodicTask(interval=IntervalSchedule()).validate_unique()
        PeriodicTask(solar=SolarSchedule()).validate_unique()
        PeriodicTask(clocked=ClockedSchedule(), one_off=True).validate_unique()


@pytest.mark.django_db
class PeriodicTaskFormHeadersTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.interval_schedule = IntervalSchedule.objects.create(every=10,
                                                                period=DAYS)

    def _form(self, headers):
        return PeriodicTaskForm(data={
            'name': 'name1',
            'task': 'task1',
            'interval': self.interval_schedule.pk,
            'args': '[]',
            'kwargs': '{}',
            'headers': headers,
        })

    def test_headers_invalid_json(self):
        form = self._form('{bad')
        self.assertFalse(form.is_valid())
        self.assertIn('Unable to parse JSON', form.errors['headers'][0])

    def test_headers_not_an_object(self):
        for headers in ('[1]', '1', '"x"', 'true', 'null'):
            with self.subTest(headers=headers):
                form = self._form(headers)
                self.assertFalse(form.is_valid())
                self.assertEqual(
                    form.errors['headers'], ['Headers must be a JSON object'],
                )

    def test_headers_object(self):
        form = self._form('{"a": 1}')
        self.assertTrue(form.is_valid(), form.errors)

    def test_headers_default(self):
        self.assertTrue(self._form('{}').is_valid())

    def test_headers_blank_saved_as_empty_object(self):
        for blank in ('', '   '):
            with self.subTest(headers=blank):
                form = self._form(blank)
                self.assertTrue(form.is_valid(), form.errors)
                task = form.save()
                self.assertEqual(task.headers, '{}')
                task.delete()


@pytest.mark.django_db
class DisableTasksTest(TestCase):

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.interval_schedule = IntervalSchedule.objects.create(every=10,
                                                                period=DAYS)

    @mock.patch('django_celery_beat.admin.PeriodicTaskAdmin.message_user')
    def test_disable_tasks(self, mock_message_user):
        PeriodicTask.objects.create(name='name1', task='task1', enabled=True,
                                    interval=self.interval_schedule)
        PeriodicTask.objects.create(name='name2', task='task2', enabled=True,
                                    interval=self.interval_schedule)

        qs = PeriodicTask.objects.all()

        PeriodicTaskAdmin(PeriodicTask, None).disable_tasks(None, qs)

        for periodic_task in qs:
            self.assertFalse(periodic_task.enabled)
            self.assertIsNone(periodic_task.last_run_at)
        mock_message_user.assert_called_once()
