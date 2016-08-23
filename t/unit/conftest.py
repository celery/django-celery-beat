from __future__ import absolute_import, unicode_literals

import pytest

from celery.utils.pytest import (  # noqa
    TestApp, Trap, app, depends_on_current_app,
)

__all__ = ['app', 'depends_on_current_app']


@pytest.fixture(scope='session', autouse=True)
def setup_default_app_trap():
    from celery._state import set_default_app
    set_default_app(Trap())


@pytest.fixture(autouse=True)
def zzzz_test_cases_calls_setup_teardown(request):
    if request.instance:
        # we set the .patching attribute for every test class.
        setup = getattr(request.instance, 'setup', None)
        # we also call .setup() and .teardown() after every test method.
        teardown = getattr(request.instance, 'teardown', None)
        setup and setup()
        teardown and request.addfinalizer(teardown)


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

        def fin():
            request.instance.app = None
        request.addfinalizer(fin)
