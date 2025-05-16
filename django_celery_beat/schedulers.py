"""Beat Scheduler Implementation."""
import datetime
import logging
import math
from multiprocessing.util import Finalize

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo  # Python 3.8

from celery import current_app, schedules
from celery.beat import ScheduleEntry, Scheduler
from celery.utils.log import get_logger
from celery.utils.time import maybe_make_aware
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.db import close_old_connections, transaction
from django.db.models import Case, F, IntegerField, Q, When
from django.db.models.functions import Cast
from django.db.utils import DatabaseError, InterfaceError
from kombu.utils.encoding import safe_repr, safe_str
from kombu.utils.json import dumps, loads

from .clockedschedule import clocked
from .models import (ClockedSchedule, CrontabSchedule, IntervalSchedule,
                     PeriodicTask, PeriodicTasks, SolarSchedule)
from .utils import NEVER_CHECK_TIMEOUT, aware_now, now

# This scheduler must wake up more frequently than the
# regular of 5 minutes because it needs to take external
# changes to the schedule into account.
DEFAULT_MAX_INTERVAL = 5  # seconds
SCHEDULE_SYNC_MAX_INTERVAL = 300  # 5 minutes

ADD_ENTRY_ERROR = """\
Cannot add entry %r to database schedule: %r. Contents: %r
"""

logger = get_logger(__name__)
debug, info, warning = logger.debug, logger.info, logger.warning


class ModelEntry(ScheduleEntry):
    """Scheduler entry taken from database row."""

    model_schedules = (
        (schedules.crontab, CrontabSchedule, 'crontab'),
        (schedules.schedule, IntervalSchedule, 'interval'),
        (schedules.solar, SolarSchedule, 'solar'),
        (clocked, ClockedSchedule, 'clocked')
    )
    save_fields = ['last_run_at', 'total_run_count', 'no_changes']

    def __init__(self, model, app=None):
        """Initialize the model entry."""
        self.app = app or current_app._get_current_object()
        self.name = model.name
        self.task = model.task
        try:
            self.schedule = model.schedule
        except model.DoesNotExist:
            logger.error(
                'Disabling schedule %s that was removed from database',
                self.name,
            )
            self._disable(model)
        try:
            self.args = loads(model.args or '[]')
            self.kwargs = loads(model.kwargs or '{}')
        except ValueError as exc:
            logger.exception(
                'Removing schedule %s for argument deseralization error: %r',
                self.name, exc,
            )
            self._disable(model)

        self.options = {}
        for option in ['queue', 'exchange', 'routing_key', 'priority']:
            value = getattr(model, option)
            if value is None:
                continue
            self.options[option] = value

        if getattr(model, 'expires_', None):
            self.options['expires'] = getattr(model, 'expires_')

        headers = loads(model.headers or '{}')
        headers['periodic_task_name'] = model.name
        self.options['headers'] = headers

        self.total_run_count = model.total_run_count
        self.model = model

        if not model.last_run_at:
            model.last_run_at = model.date_changed or self._default_now()
            # if last_run_at is not set and
            # model.start_time last_run_at should be in way past.
            # This will trigger the job to run at start_time
            # and avoid the heap block.
            if self.model.start_time:
                model.last_run_at = model.last_run_at \
                    - datetime.timedelta(days=365 * 30)

        self.last_run_at = model.last_run_at

    def _disable(self, model):
        model.no_changes = True
        model.enabled = False
        model.save()

    def is_due(self):
        if not self.model.enabled:
            # 5 second delay for re-enable.
            return schedules.schedstate(False, 5.0)

        # START DATE: only run after the `start_time`, if one exists.
        if self.model.start_time is not None:
            now = self._default_now()
            if getattr(settings, 'DJANGO_CELERY_BEAT_TZ_AWARE', True):
                now = maybe_make_aware(self._default_now())
            if now < self.model.start_time:
                # The datetime is before the start date - don't run.
                # send a delay to retry on start_time
                current_tz = now.tzinfo
                start_time = self.model.due_start_time(current_tz)
                time_remaining = start_time - now
                delay = math.ceil(time_remaining.total_seconds())

                return schedules.schedstate(False, delay)

        # EXPIRED TASK: Disable task when expired
        if self.model.expires is not None:
            now = self._default_now()
            if now >= self.model.expires:
                self._disable(self.model)
                # Don't recheck
                return schedules.schedstate(False, NEVER_CHECK_TIMEOUT)

        # ONE OFF TASK: Disable one off tasks after they've ran once
        if self.model.one_off and self.model.enabled \
                and self.model.total_run_count > 0:
            self.model.enabled = False
            self.model.total_run_count = 0  # Reset
            self.model.no_changes = False  # Mark the model entry as changed
            self.model.save()
            # Don't recheck
            return schedules.schedstate(False, NEVER_CHECK_TIMEOUT)

        # CAUTION: make_aware assumes settings.TIME_ZONE for naive datetimes,
        # while maybe_make_aware assumes utc for naive datetimes
        tz = self.app.timezone
        last_run_at_in_tz = maybe_make_aware(self.last_run_at).astimezone(tz)
        return self.schedule.is_due(last_run_at_in_tz)

    def _default_now(self):
        if getattr(settings, 'DJANGO_CELERY_BEAT_TZ_AWARE', True):
            now = datetime.datetime.now(self.app.timezone)
        else:
            # this ends up getting passed to maybe_make_aware, which expects
            # all naive datetime objects to be in utc time.
            now = datetime.datetime.utcnow()
        return now

    def __next__(self):
        self.model.last_run_at = self._default_now()
        self.model.total_run_count += 1
        self.model.no_changes = True
        return self.__class__(self.model)
    next = __next__  # for 2to3

    def save(self):
        # Object may not be synchronized, so only
        # change the fields we care about.
        obj = type(self.model)._default_manager.get(pk=self.model.pk)
        for field in self.save_fields:
            setattr(obj, field, getattr(self.model, field))

        obj.save()

    @classmethod
    def to_model_schedule(cls, schedule):
        for schedule_type, model_type, model_field in cls.model_schedules:
            schedule = schedules.maybe_schedule(schedule)
            if isinstance(schedule, schedule_type):
                model_schedule = model_type.from_schedule(schedule)
                model_schedule.save()
                return model_schedule, model_field
        raise ValueError(
            f'Cannot convert schedule type {schedule!r} to model')

    @classmethod
    def from_entry(cls, name, app=None, **entry):
        obj, created = PeriodicTask._default_manager.update_or_create(
            name=name, defaults=cls._unpack_fields(**entry),
        )
        return cls(obj, app=app)

    @classmethod
    def _unpack_fields(cls, schedule,
                       args=None, kwargs=None, relative=None, options=None,
                       **entry):
        entry_schedules = {
            model_field: None for _, _, model_field in cls.model_schedules
        }
        model_schedule, model_field = cls.to_model_schedule(schedule)
        entry_schedules[model_field] = model_schedule
        entry.update(
            entry_schedules,
            args=dumps(args or []),
            kwargs=dumps(kwargs or {}),
            **cls._unpack_options(**options or {})
        )
        return entry

    @classmethod
    def _unpack_options(cls, queue=None, exchange=None, routing_key=None,
                        priority=None, headers=None, expire_seconds=None,
                        **kwargs):
        return {
            'queue': queue,
            'exchange': exchange,
            'routing_key': routing_key,
            'priority': priority,
            'headers': dumps(headers or {}),
            'expire_seconds': expire_seconds,
        }

    def __repr__(self):
        return '<ModelEntry: {} {}(*{}, **{}) {}>'.format(
            safe_str(self.name), self.task, safe_repr(self.args),
            safe_repr(self.kwargs), self.schedule,
        )


class DatabaseScheduler(Scheduler):
    """Database-backed Beat Scheduler."""

    Entry = ModelEntry
    Model = PeriodicTask
    Changes = PeriodicTasks

    _schedule = None
    _last_timestamp = None
    _initial_read = True
    _heap_invalidated = False
    _last_full_sync = None

    def __init__(self, *args, **kwargs):
        """Initialize the database scheduler."""
        self._dirty = set()
        Scheduler.__init__(self, *args, **kwargs)
        self._finalize = Finalize(self, self.sync, exitpriority=5)
        self.max_interval = (
            kwargs.get('max_interval')
            or self.app.conf.beat_max_loop_interval
            or DEFAULT_MAX_INTERVAL)

    def setup_schedule(self):
        self.install_default_entries(self.schedule)
        self.update_from_dict(self.app.conf.beat_schedule)

    def all_as_schedule(self):
        debug('DatabaseScheduler: Fetching database schedule')
        s = {}
        for model in self.enabled_models():
            try:
                s[model.name] = self.Entry(model, app=self.app)
            except ValueError:
                pass
        return s

    def enabled_models(self):
        """Return list of enabled periodic tasks.

        Allows overriding how the list of periodic tasks is fetched without
        duplicating the filtering/querying logic.
        """
        return list(self.enabled_models_qs())

    def enabled_models_qs(self):
        next_schedule_sync = now() + datetime.timedelta(
            seconds=SCHEDULE_SYNC_MAX_INTERVAL
        )
        exclude_clock_tasks_query = Q(
            clocked__isnull=False,
            clocked__clocked_time__gt=next_schedule_sync
        )

        exclude_cron_tasks_query = self._get_crontab_exclude_query()

        # Combine the queries for optimal database filtering
        exclude_query = exclude_clock_tasks_query | exclude_cron_tasks_query

        # Fetch only the tasks we need to consider
        return self.Model.objects.enabled().exclude(exclude_query)

    def _get_crontab_exclude_query(self):
        """
        Build a query to exclude crontab tasks based on their hour value,
        adjusted for timezone differences relative to the server.

        This creates an annotation for each crontab task that represents the
        server-equivalent hour, then filters on that annotation.
        """
        # Get server time based on Django settings

        server_time = aware_now()
        server_hour = server_time.hour

        # Window of +/- 2 hours around the current hour in server tz.
        hours_to_include = [
            (server_hour + offset) % 24 for offset in range(-2, 3)
        ]
        hours_to_include += [4]  # celery's default cleanup task

        # Regex pattern to match only numbers
        # This ensures we only process numeric hour values
        numeric_hour_pattern = r'^\d+$'

        # Get all tasks with a simple numeric hour value
        numeric_hour_tasks = CrontabSchedule.objects.filter(
            hour__regex=numeric_hour_pattern
        )

        # Annotate these tasks with their server-hour equivalent
        annotated_tasks = numeric_hour_tasks.annotate(
            # Cast hour string to integer
            hour_int=Cast('hour', IntegerField()),

            # Calculate server-hour based on timezone offset
            server_hour=Case(
                # Handle each timezone specifically
                *[
                    When(
                        timezone=timezone_name,
                        then=(
                            F('hour_int')
                            + self._get_timezone_offset(timezone_name)
                            + 24
                        ) % 24
                    )
                    for timezone_name in self._get_unique_timezone_names()
                ],
                # Default case - use hour as is
                default=F('hour_int')
            )
        )

        excluded_hour_task_ids = annotated_tasks.exclude(
            server_hour__in=hours_to_include
        ).values_list('id', flat=True)

        # Build the final exclude query:
        # Exclude crontab tasks that are not in our include list
        exclude_query = Q(crontab__isnull=False) & Q(
            crontab__id__in=excluded_hour_task_ids
        )

        return exclude_query

    def _get_unique_timezone_names(self):
        """Get a list of all unique timezone names used in CrontabSchedule"""
        return CrontabSchedule.objects.values_list(
            'timezone', flat=True
        ).distinct()

    def _get_timezone_offset(self, timezone_name):
        """
        Args:
            timezone_name: The name of the timezone or a ZoneInfo object

        Returns:
            int: The hour offset
        """
        # Get server timezone
        server_time = aware_now()
        # Use server_time.tzinfo directly if it is already a ZoneInfo instance
        if isinstance(server_time.tzinfo, ZoneInfo):
            server_tz = server_time.tzinfo
        else:
            server_tz = ZoneInfo(str(server_time.tzinfo))

        if isinstance(timezone_name, ZoneInfo):
            timezone_name = timezone_name.key

        target_tz = ZoneInfo(timezone_name)

        # Use a fixed point in time for the calculation to avoid DST issues
        fixed_dt = datetime.datetime(2023, 1, 1, 12, 0, 0)

        # Calculate the offset
        dt1 = fixed_dt.replace(tzinfo=server_tz)
        dt2 = fixed_dt.replace(tzinfo=target_tz)

        # Calculate hour difference
        offset_seconds = (
            dt1.utcoffset().total_seconds() - dt2.utcoffset().total_seconds()
        )
        offset_hours = int(offset_seconds / 3600)

        return offset_hours

    def schedule_changed(self):
        try:
            close_old_connections()

            # If MySQL is running with transaction isolation level
            # REPEATABLE-READ (default), then we won't see changes done by
            # other transactions until the current transaction is
            # committed (Issue #41).
            try:
                transaction.commit()
            except transaction.TransactionManagementError:
                pass  # not in transaction management.

            last, ts = self._last_timestamp, self.Changes.last_change()
        except DatabaseError as exc:
            logger.exception('Database gave error: %r', exc)
            return False
        except InterfaceError:
            warning(
                'DatabaseScheduler: InterfaceError in schedule_changed(), '
                'waiting to retry in next call...'
            )
            return False

        try:
            if ts and ts > (last if last else ts):
                return True
        finally:
            self._last_timestamp = ts
        return False

    def reserve(self, entry):
        new_entry = next(entry)
        # Need to store entry by name, because the entry may change
        # in the mean time.
        self._dirty.add(new_entry.name)
        return new_entry

    def sync(self):
        if logger.isEnabledFor(logging.DEBUG):
            debug('Writing entries...')
        _tried = set()
        _failed = set()
        try:
            close_old_connections()

            while self._dirty:
                name = self._dirty.pop()
                try:
                    self._schedule[name].save()
                    _tried.add(name)
                except (KeyError, TypeError, ObjectDoesNotExist):
                    _failed.add(name)
        except DatabaseError as exc:
            logger.exception('Database error while sync: %r', exc)
        except InterfaceError:
            warning(
                'DatabaseScheduler: InterfaceError in sync(), '
                'waiting to retry in next call...'
            )
        finally:
            # retry later, only for the failed ones
            self._dirty |= _failed

    def update_from_dict(self, mapping):
        s = {}
        for name, entry_fields in mapping.items():
            try:
                entry = self.Entry.from_entry(name,
                                              app=self.app,
                                              **entry_fields)
                if entry.model.enabled:
                    s[name] = entry

            except Exception as exc:
                logger.exception(ADD_ENTRY_ERROR, name, exc, entry_fields)
        self.schedule.update(s)

    def install_default_entries(self, data):
        entries = {}
        if self.app.conf.result_expires:
            entries.setdefault(
                'celery.backend_cleanup', {
                    'task': 'celery.backend_cleanup',
                    'schedule': schedules.crontab('0', '4', '*'),
                    'options': {'expire_seconds': 12 * 3600},
                },
            )
        self.update_from_dict(entries)

    def schedules_equal(self, *args, **kwargs):
        if self._heap_invalidated:
            self._heap_invalidated = False
            return False
        return super().schedules_equal(*args, **kwargs)

    @property
    def schedule(self):
        initial = update = False
        current_time = datetime.datetime.now()

        if self._initial_read:
            debug('DatabaseScheduler: initial read')
            initial = update = True
            self._initial_read = False
            self._last_full_sync = current_time
        elif self.schedule_changed():
            info('DatabaseScheduler: Schedule changed.')
            update = True
            self._last_full_sync = current_time

        # Force update the schedule if it's been more than 5 minutes
        if not update:
            time_since_last_sync = (
                current_time - self._last_full_sync
            ).total_seconds()
            if (
                time_since_last_sync >= SCHEDULE_SYNC_MAX_INTERVAL
            ):
                debug(
                    'DatabaseScheduler: Forcing full sync after 5 minutes'
                )
                update = True
                self._last_full_sync = current_time

        if update:
            self.sync()
            self._schedule = self.all_as_schedule()
            # the schedule changed, invalidate the heap in Scheduler.tick
            if not initial:
                self._heap = []
                self._heap_invalidated = True
            if logger.isEnabledFor(logging.DEBUG):
                debug('Current schedule:\n%s', '\n'.join(
                    repr(entry) for entry in self._schedule.values()),
                )
        return self._schedule
