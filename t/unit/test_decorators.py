from unittest import mock, TestCase

from django_celery_beat.decorators import (
    periodic_task,
    _periodic_tasks,
    _register_all_periodic_tasks,
)


class PeriodicTaskDecoratorTests(TestCase):
    """
    Tests the @periodic_task decorator.

    NOTE: Celery registers tasks by name and will only register a task once. This causes
    a problem in testing if two test methods define a function with the same name. Celery
    thinks we are trying to register the same task twice, so it skips any future registrations.
    To avoid this issue, each task function should have a unique name -- the easiest way
    to do this is to simply append the test name to the function.
    """

    def setUp(self):
        _periodic_tasks.clear()

    @mock.patch("django_celery_beat.decorators._app.configured", False)
    def test_func_becomes_celery_task(self):
        """Test the @periodic_task decorator converts a plain function into a celery task."""

        @periodic_task(run_every=0)
        def fn_test_func_becomes_celery_task():
            pass

        self.assertTrue(hasattr(fn_test_func_becomes_celery_task, "delay"))

    @mock.patch("django_celery_beat.decorators._app.configured", False)
    def test_task_has_kwargs_as_attributes(self):
        """Test that additional kwargs to @periodic_task are set as attributes on the task."""

        @periodic_task(run_every=0, name="test-task", max_retries=3, foo="bar")
        def fn_test_task_has_kwargs_as_attributes():
            pass

        self.assertEqual(fn_test_task_has_kwargs_as_attributes.name, "test-task")
        self.assertEqual(fn_test_task_has_kwargs_as_attributes.max_retries, 3)
        self.assertEqual(fn_test_task_has_kwargs_as_attributes.foo, "bar")

    @mock.patch("django_celery_beat.decorators._app.configured", True)
    @mock.patch("django_celery_beat.decorators._app.add_periodic_task")
    def test_add_periodic_task_called_with_periodic_task_opts_when_app_ready(self, add_periodic_task_mock):
        """Test that options in periodic_task_opts are passed to app.add_periodic_task."""

        periodic_task_opts={
            "description": "test-periodic-task",
            "enabled": False,
        }

        @periodic_task(
            run_every=0,
            periodic_task_opts=periodic_task_opts,
            name="test-task",
            max_retries=3,
            foo="bar",
        )
        def fn_test_add_periodic_task_called_with_periodic_task_opts():
            pass

        self.assertEqual(add_periodic_task_mock.call_count, 1)
        self.assertEqual(
            add_periodic_task_mock.call_args[0], (0, fn_test_add_periodic_task_called_with_periodic_task_opts)
        )
        self.assertEqual(add_periodic_task_mock.call_args[1], periodic_task_opts)

        self.assertEqual(fn_test_add_periodic_task_called_with_periodic_task_opts.name, "test-task")
        self.assertEqual(fn_test_add_periodic_task_called_with_periodic_task_opts.max_retries, 3)
        self.assertEqual(fn_test_add_periodic_task_called_with_periodic_task_opts.foo, "bar")

    @mock.patch("django_celery_beat.decorators._app.configured", False)
    @mock.patch("django_celery_beat.decorators._app.add_periodic_task")
    def test_add_periodic_task_called_with_periodic_task_opts_when_app_not_ready(self, add_periodic_task_mock):
        """Test that options in periodic_task_opts are passed to app.add_periodic_task."""

        periodic_task_opts={
            "description": "test-periodic-task",
            "enabled": False,
        }

        @periodic_task(
            run_every=0,
            periodic_task_opts=periodic_task_opts,
            name="test-task",
            max_retries=3,
            foo="bar",
        )
        def fn_test_add_periodic_task_called_with_periodic_task_opts():
            pass

        self.assertEqual(add_periodic_task_mock.call_count, 0)

        _register_all_periodic_tasks()

        self.assertEqual(add_periodic_task_mock.call_count, 1)
        self.assertEqual(
            add_periodic_task_mock.call_args[0], (0, fn_test_add_periodic_task_called_with_periodic_task_opts)
        )
        self.assertEqual(add_periodic_task_mock.call_args[1], periodic_task_opts)

        self.assertEqual(fn_test_add_periodic_task_called_with_periodic_task_opts.name, "test-task")
        self.assertEqual(fn_test_add_periodic_task_called_with_periodic_task_opts.max_retries, 3)
        self.assertEqual(fn_test_add_periodic_task_called_with_periodic_task_opts.foo, "bar")

    @mock.patch("django_celery_beat.decorators._app.configured", False)
    def test_unbound_task_called_directly(self):
        """Test that an unbound task can be called directly."""

        args = ("foo", "bar")
        kwargs = {"a": 1, "b": True}

        # Setting this directly inside fn() causes scope issues so we need to use a reference object
        # that we can call a method on instead.
        actual = []

        @periodic_task(run_every=0)
        def fn_test_unbound_task_called_directly(*args, **kwargs):
            actual.append((args, kwargs))

        fn_test_unbound_task_called_directly(*args, **kwargs)

        self.assertEqual(actual[0], (args, kwargs))

    @mock.patch("django_celery_beat.decorators._app.configured", False)
    def test_bound_task_called_directly(self):
        """
        Test that a bound task can be called directly, and it will correctly pass the task
        object for the `self` parameter.
        """

        args = ("foo", "bar")
        kwargs = {"a": 1, "b": True}

        # Setting this directly inside fn() causes scope issues so we need to use a reference object
        # that we can call a method on instead.
        actual = []

        @periodic_task(bind=True, run_every=0)
        def fn_test_bound_task_called_directly(self, *args, **kwargs):
            actual.append((self, args, kwargs))

        fn_test_bound_task_called_directly(*args, **kwargs)

        self.assertEqual(actual[0], (fn_test_bound_task_called_directly, args, kwargs))

    @mock.patch("django_celery_beat.decorators._app.configured", False)
    def test_task_added_to_queue_when_not_ready(self):
        """Test that tasks are added to a queue when the Celery app is not yet configured."""

        periodic_task_opts={
            "description": "test-periodic-task",
            "enabled": False,
        }

        @periodic_task(
            run_every=123,
            periodic_task_opts=periodic_task_opts,
            kwarg_test="blah",
        )
        def fn_test_task_added_to_queue_when_not_ready():
            pass

        self.assertEqual(len(_periodic_tasks), 1)

        run_every, fn, opts = _periodic_tasks[0]

        self.assertEqual(run_every, 123)
        self.assertEqual(fn, fn_test_task_added_to_queue_when_not_ready)
        self.assertEqual(opts, periodic_task_opts)

    @mock.patch("django_celery_beat.decorators._app.configured", True)
    @mock.patch("django_celery_beat.decorators._app.add_periodic_task")
    def test_task_registered_immediately_when_app_ready(self, add_periodic_task_mock):
        """Test that when Celery is ready the task is registered immediately and not added to the queue."""

        @periodic_task(run_every=123)
        def fn_test_task_registered_immediately_when_app_ready():
            pass

        self.assertEqual(len(_periodic_tasks), 0)
        self.assertEqual(add_periodic_task_mock.call_count, 1)
        self.assertEqual(add_periodic_task_mock.call_args[0], (123, fn_test_task_registered_immediately_when_app_ready))
        self.assertEqual(add_periodic_task_mock.call_args[1], {})

    @mock.patch("django_celery_beat.decorators._app.configured", False)
    @mock.patch("django_celery_beat.decorators._app.add_periodic_task")
    def test_all_tasks_registered(self, add_periodic_task_mock):
        """Test that all tasks in the queue are registered and the queue is cleared."""

        @periodic_task(run_every=123)
        def fn1_test_all_tasks_registered():
            pass

        @periodic_task(run_every=456)
        def fn2_test_all_tasks_registered():
            pass

        self.assertEqual(len(_periodic_tasks), 2)

        _register_all_periodic_tasks()

        self.assertEqual(len(_periodic_tasks), 0)
        self.assertEqual(add_periodic_task_mock.call_count, 2)

        # Verify first task registered.
        self.assertEqual(add_periodic_task_mock.call_args_list[0][0], (123, fn1_test_all_tasks_registered))
        self.assertEqual(add_periodic_task_mock.call_args_list[0][1], {})

        # Verify second task registered.
        self.assertEqual(add_periodic_task_mock.call_args_list[1][0], (456, fn2_test_all_tasks_registered))
        self.assertEqual(add_periodic_task_mock.call_args_list[1][1], {})
