=====================================================================
 Database-backed Periodic Tasks
=====================================================================

|build-status| |coverage| |license| |wheel| |pyversion| |pyimp|

:Version: 1.0.1
:Web: http://django-celery-beat.readthedocs.io/
:Download: http://pypi.python.org/pypi/django-celery-beat
:Source: http://github.com/celery/django-celery-beat
:Keywords: django, celery, beat, periodic task, cron, scheduling

About
=====

This extension enables you to store the periodic task schedule in the
database.

The periodic tasks can be managed from the Django Admin interface, where you
can create, edit and delete periodic tasks and how often they should run.

Using the Extension
===================

Usage and installation instructions for this extension are available
from the `Celery documentation`_:

http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html#using-custom-scheduler-classes


.. _`Celery documentation`:
    http://docs.celeryproject.org/en/latest/userguide/periodic-tasks.html#using-custom-scheduler-classes

Important Warning about Time Zones
==================================

.. warning::

    If you change the Django ``TIME_ZONE`` setting your periodic task schedule
    will still be based on the old timezone.

    To fix that you would have to reset the "last run time" for each periodic
    task::

        >>> from django_celery_beat.models import PeriodicTask, PeriodicTasks
        >>> PeriodicTask.objects.all().update(last_run_at=None)
        >>> PeriodicTasks.changed()

    Note that this will reset the state as if the periodic tasks have never run
    before.

Models
======

- ``django_celery_beat.models.PeriodicTask``

This model defines a single periodic task to be run.

It must be associated with a schedule, which defines how often the task should
run.

- ``django_celery_beat.models.IntervalSchedule``

A schedule that runs at a specific interval (e.g. every 5 seconds).

- ``django_celery_beat.models.CrontabSchedule``

A schedule with fields like entries in cron:
``minute hour day-of-week day_of_month month_of_year``.

- ``django_celery_beat.models.PeriodicTasks``

This model is only used as an index to keep track of when the schedule has
changed.

Whenever you update a ``PeriodicTask`` a counter in this table is also
incremented, which tells the ``celery beat`` service to reload the schedule
from the database.

If you update periodic tasks in bulk, you will need to update the counter
manually::

    >>> from django_celery_beat.models import PeriodicTasks
    >>> PeriodicTasks.changed()

Example creating interval-based periodic task
---------------------------------------------

To create a periodic task executing at an interval you must first
create the interval object::

    >>> from django_celery_beat.models import PeriodicTask, IntervalSchedule

    # executes every 10 seconds.
    >>> schedule, created = IntervalSchedule.objects.get_or_create(
    ...     every=10,
    ...     period=IntervalSchedule.SECONDS,
    ... )

That's all the fields you need: a period type and the frequency.

You can choose between a specific set of periods:


- ``IntervalSchedule.DAYS``
- ``IntervalSchedule.HOURS``
- ``IntervalSchedule.MINUTES``
- ``IntervalSchedule.SECONDS``
- ``IntervalSchedule.MICROSECONDS``

.. note::

    If you have multiple periodic tasks executing every 10 seconds,
    then they should all point to the same schedule object.

There's also a "choices tuple" available should you need to present this
to the user::

    >>> IntervalSchedule.PERIOD_CHOICES


Now that we have defined the schedule object, we can create the periodic task
entry::

    >>> PeriodicTask.objects.create(
    ...     interval=schedule,                  # we created this above.
    ...     name='Importing contacts',          # simply describes this periodic task.
    ...     task='proj.tasks.import_contacts',  # name of task.
    ... )


Note that this is a very basic example, you can also specify the arguments
and keyword arguments used to execute the task, the ``queue`` to send it
to[*], and set an expiry time.

Here's an example specifying the arguments, note how JSON serialization is
required::

    >>> import json
    >>> from datetime import datetime, timedelta

    >>> PeriodicTask.objects.create(
    ...     interval=schedule,                  # we created this above.
    ...     name='Importing contacts',          # simply describes this periodic task.
    ...     task='proj.tasks.import_contacts',  # name of task.
    ...     args=json.dumps(['arg1', 'arg2']),
    ...     kwargs=json.dumps({
    ...        'be_careful': True,
    ...     }),
    ...     expires=datetime.utcnow() + timedelta(seconds=30)
    ... )


.. [*] you can also use low-level AMQP routing using the ``exchange`` and
       ``routing_key`` fields.

Example creating crontab-based periodic task
--------------------------------------------

A crontab schedule has the fields: ``minute``, ``hour``, ``day_of_week``,
``day_of_month`` and ``month_of_year`, so if you want the equivalent
of a ``30 * * * *`` (execute every 30 minutes) crontab entry you specify::

    >>> from django_celery_beat.models import CrontabSchedule, PeriodicTask
    >>> schedule, _ = CrontabSchedule.objects.get_or_create(
    ...     minute='30',
    ...     hour='*',
    ...     day_of_week='*',
    ...     day_of_month='*',
    ...     month_of_year='*',
    ... )


Then to create a periodic task using this schedule, use the same approach as
the interval-based periodic task earlier in this document, but instead
of ``interval=schedule``, specify ``crontab=schedule``::

    >>> PeriodicTask.objects.create(
    ...     crontab=schedule,
    ...     name='Importing contacts',
    ...     task='proj.tasks.import_contacts',
    ... )

Temporarily disable a periodic task
-----------------------------------

You can use the ``enabled`` flag to temporarily disable a periodic task::

    >>> periodic_task.enabled = False
    >>> periodic_task.save()

Installation
============

You can install django-celery-beat either via the Python Package Index (PyPI)
or from source.

To install using `pip`,::

    $ pip install -U django-celery-beat

Downloading and installing from source
--------------------------------------

Download the latest version of django-celery-beat from
http://pypi.python.org/pypi/django-celery-beat

You can install it by doing the following,::

    $ tar xvfz django-celery-beat-0.0.0.tar.gz
    $ cd django-celery-beat-0.0.0
    $ python setup.py build
    # python setup.py install

The last command must be executed as a privileged user if
you are not currently using a virtualenv.

Using the development version
-----------------------------

With pip
~~~~~~~~

You can install the latest snapshot of django-celery-beat using the following
pip command::

    $ pip install https://github.com/celery/django-celery-beat/zipball/master#egg=django-celery-beat

.. |build-status| image:: https://secure.travis-ci.org/celery/django-celery-beat.svg?branch=master
    :alt: Build status
    :target: https://travis-ci.org/celery/django-celery-beat

.. |coverage| image:: https://codecov.io/github/celery/django-celery-beat/coverage.svg?branch=master
    :target: https://codecov.io/github/celery/django-celery-beat?branch=master

.. |license| image:: https://img.shields.io/pypi/l/django-celery-beat.svg
    :alt: BSD License
    :target: https://opensource.org/licenses/BSD-3-Clause

.. |wheel| image:: https://img.shields.io/pypi/wheel/django-celery-beat.svg
    :alt: django-celery-beat can be installed via wheel
    :target: http://pypi.python.org/pypi/django-celery-beat/

.. |pyversion| image:: https://img.shields.io/pypi/pyversions/django-celery-beat.svg
    :alt: Supported Python versions.
    :target: http://pypi.python.org/pypi/django-celery-beat/

.. |pyimp| image:: https://img.shields.io/pypi/implementation/django-celery-beat.svg
    :alt: Support Python implementations.
    :target: http://pypi.python.org/pypi/django-celery-beat/

