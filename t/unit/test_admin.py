from django.test import TestCase

from django_celery_beat.admin import PeriodicTaskAdmin
from django_celery_beat.models import PeriodicTask


class ActionsTests(TestCase):
    def test_toggle_action(self):
        t1 = PeriodicTask.objects.create(name='name1', task='task1', enabled=False)
        t2 = PeriodicTask.objects.create(name='name2', task='task2', enabled=True)
        t3 = PeriodicTask.objects.create(name='name3', task='task3', enabled=False)

        qs = PeriodicTask.objects.all()
        updated_qs = PeriodicTaskAdmin(PeriodicTask, None)._get_toggle_queryset(qs)

        t1.enabled = True
        t2.enabled = False
        t3.enabled = True
        self.assertEqual(
            [t1, t2, t3],
            list(updated_qs)
        )

    def test_toggle_action_all_enabled(self):
        t1 = PeriodicTask.objects.create(name='name1', task='task1', enabled=True)
        t2 = PeriodicTask.objects.create(name='name2', task='task2', enabled=True)
        t3 = PeriodicTask.objects.create(name='name3', task='task3', enabled=True)

        qs = PeriodicTask.objects.all()
        updated_qs = PeriodicTaskAdmin(PeriodicTask, None)._get_toggle_queryset(qs)

        t1.enabled = False
        t2.enabled = False
        t3.enabled = False
        self.assertEqual(
            [t1, t2, t3],
            list(updated_qs)
        )

    def test_toggle_action_all_disabled(self):
        t1 = PeriodicTask.objects.create(name='name1', task='task1', enabled=False)
        t2 = PeriodicTask.objects.create(name='name2', task='task2', enabled=False)
        t3 = PeriodicTask.objects.create(name='name3', task='task3', enabled=False)

        qs = PeriodicTask.objects.all()
        updated_qs = PeriodicTaskAdmin(PeriodicTask, None)._get_toggle_queryset(qs)

        t1.enabled = True
        t2.enabled = True
        t3.enabled = True
        self.assertEqual(
            [t1, t2, t3],
            list(updated_qs)
        )
