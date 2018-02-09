# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_celery_beat', '0005_add_solarschedule_events_choices'),
    ]

    operations = [
        migrations.AddField(
            model_name='periodictask',
            name='origin_key',
            field=models.CharField(
                blank=True,
                default=None,
                max_length=200,
                null=True,
                verbose_name='origin key'
            ),
        ),
    ]