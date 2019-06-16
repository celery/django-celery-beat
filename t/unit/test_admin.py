from __future__ import absolute_import, unicode_literals

from itertools import combinations
from django.test import TestCase

from django_celery_beat.admin import PeriodicTaskAdmin
from django_celery_beat.models import \
    DAYS, \
    PeriodicTask, \
    CrontabSchedule, \
    IntervalSchedule, \
    SolarSchedule, \
    ClockedSchedule
from django.core.exceptions import ValidationError


class ActionsTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        super(ActionsTests, cls).setUpTestData()
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

    def test_validate_unique_raises_if_schedule_not_set(self):
        with self.assertRaises(ValidationError):
            PeriodicTask().validate_unique()

    def test_save_raises_for_multiple_schedules(self):
        schedules = [
            ('crontab', CrontabSchedule()),
            ('interval', IntervalSchedule()),
            ('solar', SolarSchedule()),
            ('clocked', ClockedSchedule())
        ]
        for i, options in enumerate(combinations(schedules, 2)):
            with self.assertRaises(ValidationError):
                PeriodicTask(name='task{}'.format(i), **dict(options)).save()

    def test_validate_unique_not_raises(self):
        PeriodicTask(crontab=CrontabSchedule()).validate_unique()
        PeriodicTask(interval=IntervalSchedule()).validate_unique()
        PeriodicTask(solar=SolarSchedule()).validate_unique()
        PeriodicTask(clocked=ClockedSchedule(), one_off=True).validate_unique()
