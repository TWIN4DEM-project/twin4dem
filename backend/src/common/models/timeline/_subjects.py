import functools
from typing import ClassVar

from django.apps import apps
from django.core import checks
from django.core.exceptions import ImproperlyConfigured
from django.db import models


class TimeFrameSubjectType(models.TextChoices):
    INSTITUTION = "institution"
    PARTY_POSITION = "party_position"


class TimeFrameMixin(models.Model):
    """A model that can occupy a time frame (a window on a timeline).

    Concrete subclasses opt in by declaring a `time_frame_subject_type` from
    `TimeFrameSubjectType` and implementing the sibling, label, and context
    rules below. They add no fields and require no migration.
    """

    time_frame_subject_type: ClassVar[str]  # a TimeFrameSubjectType value

    class Meta:
        abstract = True

    def time_frame_siblings(self) -> models.QuerySet:
        """
        The subjects that may not be active at the same time as self. Must
        exclude self.pk when it is set.
        """
        raise NotImplementedError

    def time_frame_label(self) -> str:
        """The subject's name in overlap error messages."""
        raise NotImplementedError

    def time_frame_user_settings_id(self) -> int:
        """The global context whose timelines the subject's frames apply to."""
        raise NotImplementedError


@functools.cache
def _subject_models() -> dict[str, type[TimeFrameMixin]]:
    """A cache containing the subclasses of the ``TimeFrameMixin``.

    The keys in the cache are the ``TimeFrameMixin.time_frame_subject_type``.
    The models themselves are derived from the Django app registry by calling
    ``get_models()``: a subject model cannot silently forget to register itself.
    """
    subject_models: dict[str, type[TimeFrameMixin]] = {}
    for model in apps.get_models():
        if not issubclass(model, TimeFrameMixin):
            continue
        tag = model.time_frame_subject_type
        if tag in subject_models:
            raise ImproperlyConfigured(
                f"The models {subject_models[tag].__name__} and {model.__name__} "
                f"both claim the time frame subject type '{tag}'."
            )
        subject_models[tag] = model
    return subject_models


# noinspection calling-non-callable
@checks.register("models")
def check_time_frame_subjects(app_configs=None, **kwargs):
    """Run an app-wide check to load all ``TimeFrameMixin`` subclasses."""
    errors = []
    subject_models = _subject_models()
    for tag in TimeFrameSubjectType.values:
        if tag not in subject_models:
            errors.append(
                checks.Error(
                    f"A model must opt in as the time frame subject type '{tag}'.",
                    hint=(
                        "Let the subject model inherit TimeFrameMixin and set its "
                        "time_frame_subject_type to this tag."
                    ),
                    id="common.E001",
                )
            )
    for tag, model in subject_models.items():
        if tag not in TimeFrameSubjectType.values:
            errors.append(
                checks.Error(
                    f"The model {model.__name__} opts in as the time frame "
                    f"subject type '{tag}', which is not a TimeFrameSubjectType "
                    "value.",
                    hint="Set time_frame_subject_type to a TimeFrameSubjectType value.",
                    obj=model,
                    id="common.E002",
                )
            )
    return errors


def subject_type_of(subject: TimeFrameMixin) -> str:
    """The `TimeFrameSubjectType` tag `subject` opts in with."""
    if not isinstance(subject, TimeFrameMixin):
        raise TypeError(f"{type(subject).__name__} cannot occupy a time frame")
    return subject.time_frame_subject_type
