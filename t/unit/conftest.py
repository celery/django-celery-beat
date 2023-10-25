from unittest.mock import MagicMock

import pytest
# we have to import the pytest plugin fixtures here,
# in case user did not do the `python setup.py develop` yet,
# that installs the pytest plugin into the setuptools registry.
from celery.contrib.pytest import (celery_app, celery_config,
                                   celery_enable_logging, celery_parameters,
                                   depends_on_current_app, use_celery_app_trap)
from celery.contrib.testing.app import TestApp, Trap

# Tricks flake8 into silencing redefining fixtures warnings.
__all__ = (
    'celery_app', 'celery_enable_logging', 'depends_on_current_app',
    'celery_parameters', 'celery_config', 'use_celery_app_trap'
)


@pytest.fixture(scope='session', autouse=True)
def setup_default_app_trap():
    from celery._state import set_default_app
    set_default_app(Trap())


@pytest.fixture()
def app(celery_app):
    return celery_app


@pytest.fixture(autouse=True)
def test_cases_shortcuts(request, app, patching):
    if request.instance:
        @app.task
        def add(x, y):
            return x + y

        # IMPORTANT: We set an .app attribute for every test case class.
        request.instance.app = app
        request.instance.Celery = TestApp
        request.instance.add = add
        request.instance.patching = patching
    yield
    if request.instance:
        request.instance.app = None


@pytest.fixture
def patching(monkeypatch):
    def _patching(attr):
        monkeypatch.setattr(attr, MagicMock())

    return _patching
