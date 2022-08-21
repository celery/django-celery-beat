def signals_connect():
    from django.db.models import signals, OneToOneRel
    from .models import ClockedSchedule, PeriodicTask, PeriodicTasks, IntervalSchedule, CrontabSchedule, SolarSchedule

    def o2o_discover():
        """
        Description: Discover the `OneToOneField`, and connect their signals to `PeriodicTasks.changed`.

        Issues: Signals can not connect to OneToOneField.
                https://github.com/celery/django-celery-beat/issues/572

        Note: The inheritance relationship introduces links between the child model and each of its
              parents (via an automatically-created OneToOneField).
              https://docs.djangoproject.com/en/stable/topics/db/models/#multi-table-inheritance
        """
        related_objects = PeriodicTask._meta.related_objects
        for obj in related_objects:
            if isinstance(obj, OneToOneRel):
                sender_class = obj.related_model
                signals.pre_delete.connect(PeriodicTasks.changed, sender=sender_class)
                signals.pre_save.connect(PeriodicTasks.changed, sender=sender_class)

    o2o_discover()
    signals.pre_delete.connect(PeriodicTasks.changed, sender=PeriodicTask)
    signals.pre_save.connect(PeriodicTasks.changed, sender=PeriodicTask)
    signals.pre_delete.connect(
        PeriodicTasks.update_changed, sender=IntervalSchedule)
    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=IntervalSchedule)
    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=CrontabSchedule)
    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=CrontabSchedule)
    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=SolarSchedule)
    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=SolarSchedule)
    signals.post_delete.connect(
        PeriodicTasks.update_changed, sender=ClockedSchedule)
    signals.post_save.connect(
        PeriodicTasks.update_changed, sender=ClockedSchedule)
