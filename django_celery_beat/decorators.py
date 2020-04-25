"""Task decorators."""
import functools

from celery import Celery
from celery.app import app_or_default

__all__ = ["periodic_task"]

_app = app_or_default()  # type: Celery

# A list of periodic tasks that are to be connected when Celery is ready.
# Each task is stored as a 2-tuple of (run_every, task_func).
_periodic_tasks = []


def _add_periodic_task(run_every, task):
    """
    Queues a periodic task to be registered after Celery has finished initializing,
    or registers it immediately if Celery is ready.
    """
    global _periodic_tasks

    # No need to queue tasks, they can be added immediately.
    if _app.configured:
        _app.add_periodic_task(run_every, task)
    else:
        # Register the signal callback the first time a task is queued.
        if not _periodic_tasks:
            _app.on_after_configure.connect(_register_all_periodic_tasks)

        _periodic_tasks.append((run_every, task))


def _register_all_periodic_tasks(*args, **kwargs):
    """
    Registers each task that was queued by _add_periodic_task. While it would be
    convenient to just do this directly in the `periodic_task` decorator, the problem
    there is that the signal callback is stored on the stack and becomes dead as soon
    as the decorator exits.
    """
    global _periodic_tasks

    # Add each task.
    for task in _periodic_tasks:
        _app.add_periodic_task(task[0], task[1])

    _periodic_tasks.clear()


def periodic_task(run_every, **task_kwargs):
    """
    Decorator for creating a periodic task.

    `run_every` specifies when or how often the periodic task will be scheduled to run.

    `**task_kwargs` are any additional keyword arguments that Celery accepts for tasks.
    See the 'Resources' section for a list of options.

    It supports several different types:

    - `float`: interpreted as seconds.
    - `timedelta`: interpreted as a regular time interval.
    - `celery.schedules.crontab`: interpreted as an interval using crontab notation.
    - `celery.schedules.solar`: interpreted as an interval based on solar occurences.

    ### Example

    ```
        from django_celery_beat.decorators import periodic_task
        from datetime import timedelta

        @periodic_task(run_every=timedelta(minutes=5))
        def say_hello():
            print("Hello, world!")
    ```

    ### Resources

    Info on task keyword arguments:

    https://docs.celeryproject.org/en/v4.1.0/userguide/tasks.html#list-of-options

    Info on crontab scheduling:

    https://docs.celeryproject.org/en/v4.1.0/userguide/periodic-tasks.html#crontab-schedules

    Info on solar scheduling:

    https://docs.celeryproject.org/en/v4.1.0/userguide/periodic-tasks.html#solar-schedules
    """

    def wrapper(task_func):
        # Wrap the decorated function to convert it into a celery task while also
        # preserving its original properties so that a celery worker can find it.
        @_app.task(**task_kwargs)
        @functools.wraps(task_func)
        def wrapped_task(*args, **kwargs):
            return task_func(*args, **kwargs)

        _add_periodic_task(run_every, wrapped_task)

        return wrapped_task

    return wrapper
