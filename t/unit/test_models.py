from __future__ import absolute_import, unicode_literals
import os

from django.test import TestCase
from django.apps import apps
from django.core.management import call_command
from django.db.migrations.state import ProjectState
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.questioner import NonInteractiveMigrationQuestioner

from django_celery_beat import migrations as beat_migrations


class MigrationTests(TestCase):
    def test_backward_migrations(self):
        """Test that migrating backward and forward again works.

        Ensures that django migrations can go backward and forward
        without errors.
        """
        call_command('migrate', 'django_celery_beat')
        call_command('migrate', 'django_celery_beat', '0001')
        call_command('migrate', 'django_celery_beat')

    def test_no_duplicate_migration_numbers(self):
        """Verify no duplicate migration numbers.

        Migration files with the same number can cause issues with
        backward migrations, so avoid them.
        """
        path = os.path.dirname(beat_migrations.__file__)
        files = [f[:4] for f in os.listdir(path) if f.endswith('.py')]
        self.assertEqual(
            len(files), len(set(files)),
            msg='Detected migration files with the same migration number')

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
