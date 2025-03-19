"""Periodic Task Admin interface."""
from celery import current_app
from celery.utils import cached_property
from django import forms
from django.conf import settings
from django.contrib import admin, messages
from django.db.models import Case, Value, When
from django.forms.widgets import Select
from django.template.defaultfilters import pluralize
from django.utils.translation import gettext_lazy as _
from django.utils.translation import ngettext_lazy
from kombu.utils.json import loads

from .models import (ClockedSchedule, CrontabSchedule, IntervalSchedule,
                     PeriodicTask, PeriodicTasks, SolarSchedule)
from .utils import is_database_scheduler


class TaskSelectWidget(Select):
    """Widget that lets you choose between task names."""

    celery_app = current_app
    _choices = None

    def tasks_as_choices(self):
        _ = self._modules
        tasks = sorted(name for name in self.celery_app.tasks
                       if not name.startswith('celery.'))
        return (('', ''), ) + tuple(zip(tasks, tasks))

    @property
    def choices(self):
        if self._choices is None:
            self._choices = self.tasks_as_choices()
        return self._choices

    @choices.setter
    def choices(self, _):
        # ChoiceField.__init__ sets ``self.choices = choices``
        # which would override ours.
        pass

    @cached_property
    def _modules(self):
        self.celery_app.loader.import_default_modules()


class TaskChoiceField(forms.ChoiceField):
    """Field that lets you choose between task names."""

    widget = TaskSelectWidget

    def valid_value(self, value):
        return True


class PeriodicTaskForm(forms.ModelForm):
    """Form that lets you create and modify periodic tasks."""

    regtask = TaskChoiceField(
        label=_('Task (registered)'),
        required=False,
    )
    task = forms.CharField(
        label=_('Task (custom)'),
        required=False,
        max_length=200,
    )

    class Meta:
        """Form metadata."""

        model = PeriodicTask
        exclude = ()

    def clean(self):
        data = super().clean()
        regtask = data.get('regtask')
        if regtask:
            data['task'] = regtask
        if not data['task']:
            exc = forms.ValidationError(_('Need name of task'))
            self._errors['task'] = self.error_class(exc.messages)
            raise exc

        if data.get('expire_seconds') is not None and data.get('expires'):
            raise forms.ValidationError(
                _('Only one can be set, in expires and expire_seconds')
            )
        return data

    def _clean_json(self, field):
        value = self.cleaned_data[field]
        try:
            loads(value)
        except ValueError as exc:
            raise forms.ValidationError(
                _('Unable to parse JSON: %s') % exc,
            )
        return value

    def clean_args(self):
        return self._clean_json('args')

    def clean_kwargs(self):
        return self._clean_json('kwargs')


@admin.register(PeriodicTask)
class PeriodicTaskAdmin(admin.ModelAdmin):
    """Admin-interface for periodic tasks."""

    form = PeriodicTaskForm
    model = PeriodicTask
    celery_app = current_app
    date_hierarchy = 'start_time'
    list_display = ('name', 'enabled', 'scheduler', 'interval', 'start_time',
                    'last_run_at', 'one_off')
    list_filter = ['enabled', 'one_off', 'task', 'start_time', 'last_run_at']
    actions = ('enable_tasks', 'disable_tasks', 'toggle_tasks', 'run_tasks')
    search_fields = ('name', 'task',)
    fieldsets = (
        (None, {
            'fields': ('name', 'regtask', 'task', 'enabled', 'description',),
            'classes': ('extrapretty', 'wide'),
        }),
        (_('Schedule'), {
            'fields': ('interval', 'crontab', 'crontab_translation', 'solar',
                       'clocked', 'start_time', 'last_run_at', 'one_off'),
            'classes': ('extrapretty', 'wide'),
        }),
        (_('Arguments'), {
            'fields': ('args', 'kwargs'),
            'classes': ('extrapretty', 'wide', 'collapse', 'in'),
        }),
        (_('Execution Options'), {
            'fields': ('expires', 'expire_seconds', 'queue', 'exchange',
                       'routing_key', 'priority', 'headers'),
            'classes': ('extrapretty', 'wide', 'collapse', 'in'),
        }),
    )
    readonly_fields = (
        'last_run_at', 'crontab_translation',
    )

    def crontab_translation(self, obj):
        return obj.crontab.human_readable

    change_form_template = 'admin/djcelery/change_periodictask_form.html'

    def changeform_view(self, request, object_id=None, form_url='',
                        extra_context=None):
        extra_context = extra_context or {}
        crontabs = CrontabSchedule.objects.all()
        crontab_dict = {}
        for crontab in crontabs:
            crontab_dict[crontab.id] = crontab.human_readable
        extra_context['readable_crontabs'] = crontab_dict
        return super().changeform_view(request, object_id,
                                       extra_context=extra_context)

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        scheduler = getattr(settings, 'CELERY_BEAT_SCHEDULER', None)
        extra_context['wrong_scheduler'] = not is_database_scheduler(scheduler)
        return super().changelist_view(
            request, extra_context)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('interval', 'crontab', 'solar', 'clocked')

    @admin.action(
        description=_('Enable selected tasks')
    )
    def enable_tasks(self, request, queryset):
        rows_updated = queryset.update(enabled=True)
        PeriodicTasks.update_changed()
        self.message_user(
            request,
            ngettext_lazy(
                '{0} task was successfully enabled',
                '{0} tasks were successfully enabled',
                rows_updated
            ).format(rows_updated)
        )

    @admin.action(
        description=_('Disable selected tasks')
    )
    def disable_tasks(self, request, queryset):
        rows_updated = queryset.update(enabled=False, last_run_at=None)
        PeriodicTasks.update_changed()
        self.message_user(
            request,
            ngettext_lazy(
                '{0} task was successfully disabled',
                '{0} tasks were successfully disabled',
                rows_updated
            ).format(rows_updated)
        )

    def _toggle_tasks_activity(self, queryset):
        return queryset.update(enabled=Case(
            When(enabled=True, then=Value(False)),
            default=Value(True),
        ))

    @admin.action(
        description=_('Toggle activity of selected tasks')
    )
    def toggle_tasks(self, request, queryset):
        rows_updated = self._toggle_tasks_activity(queryset)
        PeriodicTasks.update_changed()
        self.message_user(
            request,
            ngettext_lazy(
                '{0} task was successfully toggled',
                '{0} tasks were successfully toggled',
                rows_updated
            ).format(rows_updated)
        )

    @admin.action(
        description=_('Run selected tasks')
    )
    def run_tasks(self, request, queryset):
        self.celery_app.loader.import_default_modules()
        tasks = [(self.celery_app.tasks.get(task.task),
                  loads(task.args),
                  loads(task.kwargs),
                  task.queue,
                  task.name)
                 for task in queryset]

        if any(t[0] is None for t in tasks):
            for i, t in enumerate(tasks):
                if t[0] is None:
                    break

            # variable "i" will be set because list "tasks" is not empty
            not_found_task_name = queryset[i].task

            self.message_user(
                request,
                _(f'task "{not_found_task_name}" not found'),
                level=messages.ERROR,
            )
            return

        task_ids = [
            task.apply_async(
                args=args,
                kwargs=kwargs,
                queue=queue,
                headers={'periodic_task_name': periodic_task_name}
            )
            if queue and len(queue)
            else task.apply_async(
                args=args,
                kwargs=kwargs,
                headers={'periodic_task_name': periodic_task_name}
            )
            for task, args, kwargs, queue, periodic_task_name in tasks
        ]
        tasks_run = len(task_ids)
        self.message_user(
            request,
            _('{0} task{1} {2} successfully run').format(
                tasks_run,
                pluralize(tasks_run),
                pluralize(tasks_run, _('was,were')),
            ),
        )


class PeriodicTaskInline(admin.TabularInline):
    model = PeriodicTask
    fields = ('name', 'task', 'args', 'kwargs')
    readonly_fields = fields
    can_delete = False
    extra = 0
    show_change_link = True
    verbose_name = "Periodic Tasks Using This Schedule"
    verbose_name_plural = verbose_name

    def has_add_permission(self, request, obj):
        return False


class ScheduleAdmin(admin.ModelAdmin):
    inlines = [PeriodicTaskInline]


@admin.register(ClockedSchedule)
class ClockedScheduleAdmin(ScheduleAdmin):
    """Admin-interface for clocked schedules."""

    fields = (
        'clocked_time',
    )
    list_display = (
        'clocked_time',
    )


@admin.register(CrontabSchedule)
class CrontabScheduleAdmin(ScheduleAdmin):
    """Admin class for CrontabSchedule."""

    list_display = ('__str__', 'human_readable')
    fields = ('human_readable', 'minute', 'hour', 'day_of_month',
              'month_of_year', 'day_of_week', 'timezone')
    readonly_fields = ('human_readable', )


@admin.register(SolarSchedule)
class SolarScheduleAdmin(ScheduleAdmin):
    """Admin class for SolarSchedule."""
    pass


@admin.register(IntervalSchedule)
class IntervalScheduleAdmin(ScheduleAdmin):
    """Admin class for IntervalSchedule."""
    pass
