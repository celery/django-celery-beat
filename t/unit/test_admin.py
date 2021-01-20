import pytest
from django.core.exceptions import ValidationError
from django.test import TestCase
from itertools import combinations

from django_celery_beat.admin import PeriodicTaskAdmin
from django_celery_beat.models import \
    DAYS, \
    PeriodicTask, \
    CrontabSchedule, \
    IntervalSchedule, \
    SolarSchedule, \
    ClockedSchedule


@pytest.mark.django_db()
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


@pytest.mark.django_db()
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
            name = 'task{}'.format(i)
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
