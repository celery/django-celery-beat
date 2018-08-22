from django.test import TestCase

from django_celery_beat.admin import PeriodicTaskAdmin
from django_celery_beat.models import PeriodicTask


class ActionsTests(TestCase):
    def test_toggle_action(self):
        PeriodicTask.objects.create(name='name1', task='task1', enabled=False)
        PeriodicTask.objects.create(name='name2', task='task2', enabled=True)
        PeriodicTask.objects.create(name='name3', task='task3', enabled=False)

        qs = PeriodicTask.objects.all()
        PeriodicTaskAdmin(PeriodicTask, None)._toggle_tasks_activity(qs)

        self.assertTrue(PeriodicTask.objects.get(name='name1', task='task1').enabled)
        self.assertFalse(PeriodicTask.objects.get(name='name2', task='task2').enabled)
        self.assertTrue(PeriodicTask.objects.get(name='name3', task='task3').enabled)

    def test_toggle_action_all_enabled(self):
        PeriodicTask.objects.create(name='name1', task='task1', enabled=True)
        PeriodicTask.objects.create(name='name2', task='task2', enabled=True)
        PeriodicTask.objects.create(name='name3', task='task3', enabled=True)

        qs = PeriodicTask.objects.all()
        PeriodicTaskAdmin(PeriodicTask, None)._toggle_tasks_activity(qs)

        self.assertFalse(PeriodicTask.objects.get(name='name1', task='task1').enabled)
        self.assertFalse(PeriodicTask.objects.get(name='name2', task='task2').enabled)
        self.assertFalse(PeriodicTask.objects.get(name='name3', task='task3').enabled)

    def test_toggle_action_all_disabled(self):
        PeriodicTask.objects.create(name='name1', task='task1', enabled=False)
        PeriodicTask.objects.create(name='name2', task='task2', enabled=False)
        PeriodicTask.objects.create(name='name3', task='task3', enabled=False)

        qs = PeriodicTask.objects.all()
        PeriodicTaskAdmin(PeriodicTask, None)._toggle_tasks_activity(qs)

        self.assertTrue(PeriodicTask.objects.get(name='name1', task='task1').enabled)
        self.assertTrue(PeriodicTask.objects.get(name='name2', task='task2').enabled)
        self.assertTrue(PeriodicTask.objects.get(name='name3', task='task3').enabled)
