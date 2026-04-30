# flake8: noqa
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('django_celery_beat', '0019_alter_periodictasks_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='periodictask',
            name='from_configuration',
            field=models.BooleanField(
                default=False,
                editable=False,
                help_text=(
                    'Set automatically when the task is imported from the '
                    'celery beat_schedule configuration. Edits made here '
                    'will be reverted on the next celery beat startup. '
                    'Remove the entry from beat_schedule to manage this '
                    'task only via the database.'
                ),
                verbose_name='From configuration',
            ),
        ),
    ]
