import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings

from django_celery_beat.helpers import (clockedschedule_model,
                                        crontabschedule_model,
                                        intervalschedule_model,
                                        periodictask_model,
                                        periodictasks_model,
                                        solarschedule_model)
from django_celery_beat.models.abstract import (AbstractClockedSchedule,
                                                AbstractCrontabSchedule,
                                                AbstractIntervalSchedule,
                                                AbstractPeriodicTask,
                                                AbstractPeriodicTasks,
                                                AbstractSolarSchedule)

fetch_models = [
    (AbstractCrontabSchedule, crontabschedule_model),
    (AbstractIntervalSchedule, intervalschedule_model),
    (AbstractPeriodicTask, periodictask_model),
    (AbstractSolarSchedule, solarschedule_model),
    (AbstractPeriodicTasks, periodictasks_model),
    (AbstractClockedSchedule, clockedschedule_model),
]


@pytest.mark.django_db
@pytest.mark.parametrize(("abstract_model", "fetch_func"), fetch_models)
def test_fetching_model_works_with_no_setting(abstract_model, fetch_func):
    """
    Test fetching models when you're using the generic Django Celery Beat models.
    """
    result = fetch_func()
    assert issubclass(
        result, abstract_model
    ), f"Expected {abstract_model}, got {type(result)}"


@pytest.mark.django_db
@pytest.mark.parametrize(("abstract_model", "fetch_func"), fetch_models)
def test_fetching_model_works_with_correct_setting(abstract_model, fetch_func):
    """
    Test fetching models when you're using custom Django Celery Beat models.
    """
    model_name = abstract_model.__name__.replace("Abstract", "")
    model_setting_name = f"CELERY_BEAT_{model_name.upper()}_MODEL"
    app_label_and_generic_name = f"django_celery_beat.{model_name.upper()}"

    with override_settings(**{model_setting_name: app_label_and_generic_name}):
        result = fetch_func()
        assert issubclass(
            result, abstract_model
        ), f"Expected {abstract_model}, got {type(result)}"


@pytest.mark.django_db
@pytest.mark.parametrize(("abstract_model", "fetch_func"), fetch_models)
def test_fetching_model_works_with_invalid_setting(abstract_model, fetch_func):
    """
    Test fetching models when you're using custom Django Celery Beat models,
    but your model name is not of the form `app_label.model_name`.
    """
    model_name = abstract_model.__name__.replace("Abstract", "")
    model_setting_name = f"CELERY_BEAT_{model_name.upper()}_MODEL"

    with override_settings(**{model_setting_name: f"{model_name}"}), pytest.raises(
        ImproperlyConfigured,
        match=f"{model_setting_name} must be of the form 'app_label.model_name'",
    ):
        fetch_func()


@pytest.mark.django_db
@pytest.mark.parametrize(("abstract_model", "fetch_func"), fetch_models)
def test_fetching_model_works_with_improper_setting(abstract_model, fetch_func):
    """
    Test fetching models when you're using custom Django Celery Beat models,
    but your model cannot be found.
    """
    model_name = abstract_model.__name__.replace("Abstract", "")
    model_setting_name = f"CELERY_BEAT_{model_name.upper()}_MODEL"

    with override_settings(
        **{model_setting_name: f"improper.{model_name}"}
    ), pytest.raises(
        ImproperlyConfigured,
        match=f"{model_setting_name} refers to model 'improper.{model_name}' "
        "that has not been installed",
    ):
        fetch_func()
