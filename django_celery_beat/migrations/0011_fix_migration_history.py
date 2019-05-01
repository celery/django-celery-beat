from __future__ import absolute_import, unicode_literals

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('django_celery_beat', '0010_auto_20190429_0326'),
    ]

    operations = [
        # delete the squashed migration history of migrations replaced by
        # 0005_add_solarschedule_events_choices_squashed_0009_merge_20181012_1416
        # the squashed file was convertd to a normal migration and the py files
        # were deleted, so we must also delete them from the history.
        # this is necessary because the squashed file was somehow screwing up
        # this history for version 1.3.0 installs that were upgraded.
        migrations.RunSQL([(
            """
            delete from django_migrations where app='django_celery_beat' and (
            name = '0005_add_solarschedule_events_choices'
            or name = '0006_auto_20180210_1226'
            or name = '0006_auto_20180322_0932'
            or name = '0007_auto_20180521_0826'
            or name = '0008_auto_20180914_1922'
            )
            """, None)],
            reverse_sql=migrations.RunSQL.noop
        ),
    ]
