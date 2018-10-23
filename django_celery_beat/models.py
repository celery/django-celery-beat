"""Database models."""
from __future__ import absolute_import, unicode_literals

from datetime import timedelta

import timezone_field
from celery import schedules
from celery.five import python_2_unicode_compatible
from django.core.exceptions import MultipleObjectsReturned, ValidationError
from django.core.validators import MaxValueValidator
from django.db import models
from django.db.models import signals
from django.utils.translation import ugettext_lazy as _

from . import managers, validators
from .tzcrontab import TzAwareCrontab
from .utils import make_aware, now


DAYS = 'days'
HOURS = 'hours'
MINUTES = 'minutes'
SECONDS = 'seconds'
MICROSECONDS = 'microseconds'

PERIOD_CHOICES = (
    (DAYS, _('Days')),
    (HOURS, _('Hours')),
    (MINUTES, _('Minutes')),
    (SECONDS, _('Seconds')),
    (MICROSECONDS, _('Microseconds')),
)

SOLAR_SCHEDULES = [(x, _(x)) for x in sorted(schedules.solar._all_events)]


def cronexp(field):
    """Representation of cron expression."""
    return field and str(field).replace(' ', '') or '*'


@python_2_unicode_compatible
class SolarSchedule(models.Model):
    """Schedule following astronomical patterns."""

    event = models.CharField(
        _('event'), max_length=24, choices=SOLAR_SCHEDULES
    )
    latitude = models.DecimalField(
        _('latitude'), max_digits=9, decimal_places=6
    )
    longitude = models.DecimalField(
        _('longitude'), max_digits=9, decimal_places=6
    )

    class Meta:
        """Table information."""

        verbose_name = _('solar event')
        verbose_name_plural = _('solar events')
        ordering = ('event', 'latitude', 'longitude')
        unique_together = ('event', 'latitude', 'longitude')

    @property
    def schedule(self):
        return schedules.solar(self.event,
                               self.latitude,
                               self.longitude,
                               nowfun=lambda: make_aware(now()))

    @classmethod
    def from_schedule(cls, schedule):
        spec = {'event': schedule.event,
                'latitude': schedule.lat,
                'longitude': schedule.lon}
        try:
            return cls.objects.get(**spec)
        except cls.DoesNotExist:
            return cls(**spec)
        except MultipleObjectsReturned:
            cls.objects.filter(**spec).delete()
            return cls(**spec)

    def __str__(self):
        return '{0} ({1}, {2})'.format(
            self.get_event_display(),
            self.latitude,
            self.longitude
        )


@python_2_unicode_compatible
class IntervalSchedule(models.Model):
    """Schedule executing every n seconds."""

    DAYS = DAYS
    HOURS = HOURS
    MINUTES = MINUTES
    SECONDS = SECONDS
    MICROSECONDS = MICROSECONDS

    PERIOD_CHOICES = PERIOD_CHOICES

    every = models.IntegerField(_('every'), null=False)
    period = models.CharField(
        _('period'), max_length=24, choices=PERIOD_CHOICES,
    )

    class Meta:
        """Table information."""

        verbose_name = _('interval')
        verbose_name_plural = _('intervals')
        ordering = ['period', 'every']

    @property
    def schedule(self):
        return schedules.schedule(
            timedelta(**{self.period: self.every}),
            nowfun=lambda: make_aware(now())
        )

    @classmethod
    def from_schedule(cls, schedule, period=SECONDS):
        every = max(schedule.run_every.total_seconds(), 0)
        try:
            return cls.objects.get(every=every, period=period)
        except cls.DoesNotExist:
            return cls(every=every, period=period)
        except MultipleObjectsReturned:
            cls.objects.filter(every=every, period=period).delete()
            return cls(every=every, period=period)

    def __str__(self):
        if self.every == 1:
            return _('every {0.period_singular}').format(self)
        return _('every {0.every} {0.period}').format(self)

    @property
    def period_singular(self):
        return self.period[:-1]


@python_2_unicode_compatible
class CrontabSchedule(models.Model):
    """Timezone Aware Crontab-like schedule."""

    #
    # The worst case scenario for day of month is a list of all 31 day numbers
    # '[1, 2, ..., 31]' which has a length of 115. Likewise, minute can be
    # 0..59 and hour can be 0..23. Ensure we can accomodate these by allowing
    # 4 chars for each value (what we save on 0-9 accomodates the []).
    # We leave the other fields at their historical length.
    #
    minute = models.CharField(
        _('minute'), max_length=60 * 4, default='*',
        validators=[validators.minute_validator],
    )
    hour = models.CharField(
        _('hour'), max_length=24 * 4, default='*',
        validators=[validators.hour_validator],
    )
    day_of_week = models.CharField(
        _('day of week'), max_length=64, default='*',
        validators=[validators.day_of_week_validator],
    )
    day_of_month = models.CharField(
        _('day of month'), max_length=31 * 4, default='*',
        validators=[validators.day_of_month_validator],
    )
    month_of_year = models.CharField(
        _('month of year'), max_length=64, default='*',
        validators=[validators.month_of_year_validator],
    )

    timezone = timezone_field.TimeZoneField(default='UTC')

    class Meta:
        """Table information."""

        verbose_name = _('crontab')
        verbose_name_plural = _('crontabs')
        ordering = ['month_of_year', 'day_of_month',
                    'day_of_week', 'hour', 'minute', 'timezone']

    def __str__(self):
        return '{0} {1} {2} {3} {4} (m/h/d/dM/MY) {5}'.format(
            cronexp(self.minute), cronexp(self.hour),
            cronexp(self.day_of_week), cronexp(self.day_of_month),
            cronexp(self.month_of_year), str(self.timezone)
        )

    @property
    def schedule(self):
        return TzAwareCrontab(
            minute=self.minute,
            hour=self.hour, day_of_week=self.day_of_week,
            day_of_month=self.day_of_month,
            month_of_year=self.month_of_year,
            tz=self.timezone
        )

    @classmethod
    def from_schedule(cls, schedule):
        spec = {'minute': schedule._orig_minute,
                'hour': schedule._orig_hour,
                'day_of_week': schedule._orig_day_of_week,
                'day_of_month': schedule._orig_day_of_month,
                'month_of_year': schedule._orig_month_of_year,
                'timezone': schedule.tz
                }
        try:
            return cls.objects.get(**spec)
        except cls.DoesNotExist:
            return cls(**spec)
        except MultipleObjectsReturned:
            cls.objects.filter(**spec).delete()
            return cls(**spec)


class PeriodicTasks(models.Model):
    """Helper table for tracking updates to periodic tasks."""

    ident = models.SmallIntegerField(default=1, primary_key=True, unique=True)
    last_update = models.DateTimeField(null=False)

    objects = managers.ExtendedManager()

    @classmethod
    def changed(cls, instance, **kwargs):
        if not instance.no_changes:
            cls.update_changed()

    @classmethod
    def update_changed(cls, **kwargs):
        cls.objects.update_or_create(ident=1, defaults={'last_update': now()})

    @classmethod
    def last_change(cls):
        try:
            return cls.objects.get(ident=1).last_update
        except cls.DoesNotExist:
            pass


@python_2_unicode_compatible
class PeriodicTask(models.Model):
    """Model representing a periodic task."""

    name = models.CharField(
        _('name'), max_length=200, unique=True,
        help_text=_('Useful description'),
    )
    task = models.CharField(_('task name'), max_length=200)
    interval = models.ForeignKey(
        IntervalSchedule, on_delete=models.CASCADE,
        null=True, blank=True, verbose_name=_('interval'),
    )
    crontab = models.ForeignKey(
        CrontabSchedule, on_delete=models.CASCADE, null=True, blank=True,
        verbose_name=_('crontab'), help_text=_('Use one of interval/crontab'),
    )
    solar = models.ForeignKey(
        SolarSchedule, on_delete=models.CASCADE, null=True, blank=True,
        verbose_name=_('solar'), help_text=_('Use a solar schedule')
    )
    args = models.TextField(
        _('Arguments'), blank=True, default='[]',
        help_text=_('JSON encoded positional arguments'),
    )
    kwargs = models.TextField(
        _('Keyword arguments'), blank=True, default='{}',
        help_text=_('JSON encoded keyword arguments'),
    )
    queue = models.CharField(
        _('queue'), max_length=200, blank=True, null=True, default=None,
        help_text=_('Queue defined in CELERY_TASK_QUEUES'),
    )
    exchange = models.CharField(
        _('exchange'), max_length=200, blank=True, null=True, default=None,
    )
    routing_key = models.CharField(
        _('routing key'), max_length=200, blank=True, null=True, default=None,
    )
    priority = models.PositiveIntegerField(
        _('priority'), default=None, validators=[MaxValueValidator(255)],
        blank=True, null=True
    )
    expires = models.DateTimeField(
        _('expires'), blank=True, null=True,
    )
    one_off = models.BooleanField(
        _('one-off task'), default=False,
    )
    start_time = models.DateTimeField(
        _('start_time'), blank=True, null=True,
    )
    enabled = models.BooleanField(
        _('enabled'), default=True,
    )
    last_run_at = models.DateTimeField(
        auto_now=False, auto_now_add=False,
        editable=False, blank=True, null=True,
    )
    total_run_count = models.PositiveIntegerField(
        default=0, editable=False,
    )
    date_changed = models.DateTimeField(auto_now=True)
    description = models.TextField(_('description'), blank=True)

    objects = managers.PeriodicTaskManager()
    no_changes = False

    class Meta:
        """Table information."""

        verbose_name = _('periodic task')
        verbose_name_plural = _('periodic tasks')

    def validate_unique(self, *args, **kwargs):
        super(PeriodicTask, self).validate_unique(*args, **kwargs)

        schedule_types = ['interval', 'crontab', 'solar']
        selected_schedule_types = [s for s in schedule_types
                                   if getattr(self, s)]

        if len(selected_schedule_types) == 0:
            raise ValidationError({
                'interval': [
                    'One of interval, crontab, or solar must be set.'
                ]
            })

        err_msg = 'Only one of interval, crontab, or solar must be set'
        if len(selected_schedule_types) > 1:
            error_info = {}
            for selected_schedule_type in selected_schedule_types:
                error_info[selected_schedule_type] = [err_msg]
            raise ValidationError(error_info)

    def save(self, *args, **kwargs):
        self.exchange = self.exchange or None
        self.routing_key = self.routing_key or None
        self.queue = self.queue or None
        if not self.enabled:
            self.last_run_at = None
        super(PeriodicTask, self).save(*args, **kwargs)

    def __str__(self):
        fmt = '{0.name}: {{no schedule}}'
        if self.interval:
            fmt = '{0.name}: {0.interval}'
        if self.crontab:
            fmt = '{0.name}: {0.crontab}'
        if self.solar:
            fmt = '{0.name}: {0.solar}'
        return fmt.format(self)

    @property
    def schedule(self):
        if self.interval:
            return self.interval.schedule
        if self.crontab:
            return self.crontab.schedule
        if self.solar:
            return self.solar.schedule


signals.pre_delete.connect(PeriodicTasks.changed, sender=PeriodicTask)
signals.pre_save.connect(PeriodicTasks.changed, sender=PeriodicTask)
signals.pre_delete.connect(
    PeriodicTasks.update_changed, sender=IntervalSchedule)
signals.post_save.connect(
    PeriodicTasks.update_changed, sender=IntervalSchedule)
signals.post_delete.connect(
    PeriodicTasks.update_changed, sender=CrontabSchedule)
signals.post_save.connect(
    PeriodicTasks.update_changed, sender=CrontabSchedule)
signals.post_delete.connect(
    PeriodicTasks.update_changed, sender=SolarSchedule)
signals.post_save.connect(
    PeriodicTasks.update_changed, sender=SolarSchedule)
