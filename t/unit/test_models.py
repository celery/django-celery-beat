from __future__ import absolute_import, unicode_literals
import importlib
import os

from django.apps import apps
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner
from django.db.migrations.state import ProjectState
from django.test import TestCase, override_settings
from django.utils import six

from django_celery_beat import migrations as beat_migrations, models


class ModelMigrationTests(TestCase):
    def test_periodic_task_name_max_length_defaults_to_200_in_model(self):
        six.moves.reload_module(models)
        self.assertEqual(
            200, models.PeriodicTask._meta.get_field('name').max_length)

    @override_settings(DJANGO_CELERY_BEAT_NAME_MAX_LENGTH=191)
    def test_periodic_task_name_max_length_changed_to_191_in_model(self):
        six.moves.reload_module(models)
        self.assertEqual(
            191, models.PeriodicTask._meta.get_field('name').max_length)

    def test_periodic_task_name_max_length_defaults_to_200_in_migration(self):
        initial_migration_module = importlib.import_module(
            'django_celery_beat.migrations.0001_initial')
        six.moves.reload_module(initial_migration_module)
        initial_migration = initial_migration_module.Migration
        periodic_task_creation = initial_migration.operations[2]
        fields = dict(periodic_task_creation.fields)

        self.assertEqual('PeriodicTask', periodic_task_creation.name)
        self.assertEqual(200, fields['name'].max_length)

    @override_settings(DJANGO_CELERY_BEAT_NAME_MAX_LENGTH=191)
    def test_periodic_task_name_max_length_changed_to_191_in_migration(self):
        initial_migration_module = importlib.import_module(
            'django_celery_beat.migrations.0001_initial')
        six.moves.reload_module(initial_migration_module)
        initial_migration = initial_migration_module.Migration
        periodic_task_creation = initial_migration.operations[2]
        fields = dict(periodic_task_creation.fields)

        self.assertEqual('PeriodicTask', periodic_task_creation.name)
        self.assertEqual(191, fields['name'].max_length)


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
