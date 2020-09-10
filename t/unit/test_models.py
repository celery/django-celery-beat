import os
import random
import string

import dill
import timezone_field
from celery.canvas import Signature
from django.apps import apps
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState
from django.test import TestCase, override_settings

from django_celery_beat import migrations as beat_migrations
from django_celery_beat.models import crontab_schedule_celery_timezone, PeriodicTask, IntervalSchedule
from django_celery_beat.utils import sign_task_signature, generate_keys


class MigrationTests(TestCase):
    def test_no_future_duplicate_migration_numbers(self):
        """Verify no duplicate migration numbers.

        Migration files with the same number can cause issues with
        backward migrations, so avoid them.
        """
        path = os.path.dirname(beat_migrations.__file__)
        files = [f[:4] for f in os.listdir(path) if f.endswith('.py')]
        expected_duplicates = [
            (3, '0006'),
        ]
        duplicates_extra = sum(count - 1 for count, _ in expected_duplicates)
        duplicates_numbers = [number for _, number in expected_duplicates]
        self.assertEqual(
            len(files), len(set(files)) + duplicates_extra,
            msg=('Detected migration files with the same migration number'
                 ' (besides {})'.format(' and '.join(duplicates_numbers))))

    def test_models_match_migrations(self):
        """Make sure that no model changes exist.

        This logic is taken from django's makemigrations.py file.
        Here just detect if model changes exist that require
        a migration, and if so we fail.
        """
        app_labels = ['django_celery_beat']
        loader = MigrationLoader(None, ignore_no_migrations=True)
        questioner = NonInteractiveMigrationQuestioner(
            specified_apps=app_labels, dry_run=False)
        autodetector = MigrationAutodetector(
            loader.project_state(),
            ProjectState.from_apps(apps),
            questioner,
        )
        changes = autodetector.changes(
            graph=loader.graph,
            trim_to_apps=app_labels,
            convert_apps=app_labels,
            migration_name='fake_name',
        )
        self.assertTrue(
            not changes,
            msg='Model changes exist that do not have a migration')


class CrontabScheduleTestCase(TestCase):
    FIRST_VALID_TIMEZONE = timezone_field.TimeZoneField.CHOICES[0][0].zone

    def test_default_timezone_without_settings_config(self):
        assert crontab_schedule_celery_timezone() == "UTC"

    @override_settings(CELERY_TIMEZONE=FIRST_VALID_TIMEZONE)
    def test_default_timezone_with_settings_config(self):
        assert crontab_schedule_celery_timezone() == self.FIRST_VALID_TIMEZONE


class PeriodicTaskSignatureTestCase(TestCase):
    test_private_key_path = './test_id_rsa'
    test_public_key_path = './test_id_rsa.pub'

    @classmethod
    def setUpClass(cls):
        super(PeriodicTaskSignatureTestCase, cls).setUpClass()

        os.environ.update({
            'DJANGO_CELERY_BEAT_PRIVATE_KEY_PATH': cls.test_private_key_path,
            'DJANGO_CELERY_BEAT_PUBLIC_KEY_PATH': cls.test_public_key_path,
        })

        generate_keys(
            private_key_path=cls.test_private_key_path,
            public_key_path=cls.test_public_key_path
        )

    def test_periodic_task_with_signatures(self):
        empty_task_signature = Signature(task='empty_task')

        serialized_empty_task = dill.dumps(empty_task_signature)
        s = sign_task_signature(serialized_empty_task)

        interval, _ = IntervalSchedule.objects.get_or_create(
            every=2,
            period=IntervalSchedule.MINUTES
        )
        periodic_task = PeriodicTask.objects.create(
            name='test-' + ''.join(random.choices(string.ascii_letters, k=20)),
            task_signature=serialized_empty_task,
            task_signature_sign=s,
            callback_signature=serialized_empty_task,
            callback_signature_sign=s,
            interval=interval,
        )

        task_signature = periodic_task.get_verified_callback_signature(raise_exceptions=False)
        callback_signature = periodic_task.get_verified_callback_signature(raise_exceptions=False)

        self.assertEqual(empty_task_signature, task_signature)
        self.assertEqual(empty_task_signature, callback_signature)

    @classmethod
    def tearDownClass(cls) -> None:
        super(PeriodicTaskSignatureTestCase, cls).tearDownClass()

        if os.path.exists(cls.test_private_key_path):
            os.remove(cls.test_private_key_path)

        if os.path.exists(cls.test_public_key_path):
            os.remove(cls.test_public_key_path)
