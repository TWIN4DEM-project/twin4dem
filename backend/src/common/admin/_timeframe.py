from collections import defaultdict

from django import forms
from django.contrib import admin

from ..models import TimeFrameModel, TimeFrameSubject, VirtualTimeline
from ..models.timeline import TimeFrameSubjectSiblings


class TimelineSelectionFormMixin:
    _SELECTION_FIELD_KEY = "timeline_selection"

    @staticmethod
    def timeline_selection_field() -> forms.ModelMultipleChoiceField:
        # not the `timelines` model field: the frame must be validated together
        # with its timelines, before anything is saved
        return forms.ModelMultipleChoiceField(
            queryset=VirtualTimeline.objects.none(),
            required=False,
            label="Timelines",
            help_text="Leave empty to apply the time frame to all timelines.",
        )

    def __init__(self, *args, user_settings_id: int | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields[self._SELECTION_FIELD_KEY].queryset = (
            VirtualTimeline.objects.filter(user_settings_id=user_settings_id)
        )
        frame = self.frame_to_edit()
        if frame is not None and frame.pk is not None:
            self.initial[self._SELECTION_FIELD_KEY] = frame.timelines.all()

    def frame_to_edit(self) -> TimeFrameModel | None:
        return self.instance

    def time_frame(self) -> TimeFrameModel:
        """The frame described by the form, not saved yet."""
        raise NotImplementedError

    def time_frame_subject(self) -> TimeFrameSubject | None:
        return getattr(self.time_frame(), "subject", None)

    def selected_timelines(self) -> list[VirtualTimeline]:
        return list(self.cleaned_data.get(self._SELECTION_FIELD_KEY) or ())

    def selected_timeline_ids(self) -> list[int] | None:
        return [timeline.pk for timeline in self.selected_timelines()] or None

    def add_conflict_errors(
        self,
        other_subject: TimeFrameSubject,
        other_frame: TimeFrameModel | None,
        labels: dict[int, str],
        *,
        same_subject: bool,
    ) -> None:
        """Report a conflict between the form's frame and another frame.

        ``other_frame=None`` means the other subject has no time frame, so it is
        active at all times on all timelines.
        """
        frame = self.time_frame()
        if other_frame is None:
            if not same_subject:
                self.add_error(
                    None,
                    f"{other_subject.time_frame_label()} has no time frame, so it "
                    f"is active at all times on all timelines.",
                )
            return
        if not frame.shares_timeline_with(other_frame):
            return
        if same_subject:
            self.add_error(
                None,
                f"{self.time_frame_subject().time_frame_label()} already occupies "
                f"the time frame {other_frame.format_interval()} on "
                f"{frame.format_timelines(other_frame, labels)}.",
            )
            return
        if not frame.overlaps(other_frame):
            return
        self.add_error(
            None,
            f"Overlaps with {other_subject.time_frame_label()} "
            f"{other_frame.format_interval()} on "
            f"{frame.format_timelines(other_frame, labels)}.",
        )


class CurrentSettingsInlineMixin:
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        settings = request.current_settings
        formset.user_settings_id = settings.pk if settings is not None else None
        return formset


class TimeFrameInlineForm(TimelineSelectionFormMixin, forms.ModelForm):
    timeline_selection = TimelineSelectionFormMixin.timeline_selection_field()

    class Meta:
        fields = ("valid_from", "valid_to")

    def time_frame(self) -> TimeFrameModel:
        return self.instance

    def clean(self):
        cleaned_data = super().clean()
        self.instance.pending_timeline_ids = self.selected_timeline_ids()
        return cleaned_data

    def save_time_frame(self):
        if self.cleaned_data.get("DELETE") or not self.instance.pk:
            return
        self.instance.timelines.set(self.selected_timelines())


class TimeFrameInlineAdminMixin:
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        for formset in formsets:
            for inline_form in formset.forms:
                save_time_frame = getattr(inline_form, "save_time_frame", None)
                if save_time_frame is not None:
                    save_time_frame()


class TimeFrameInlineFormSet(forms.BaseInlineFormSet):
    # the inline binds this to the administration's current global context
    user_settings_id: int | None = None

    def get_form_kwargs(self, index):
        return {
            **super().get_form_kwargs(index),
            "user_settings_id": self.user_settings_id,
        }

    def _timeline_labels(self) -> dict[int, str]:
        """The current context's timelines, by id and label."""
        timelines = VirtualTimeline.objects.filter(
            user_settings_id=self.user_settings_id
        )
        return dict(timelines.values_list("id", "label"))

    def validate_time_frames(self, submitted: list[forms.Form]) -> None:
        """Validate the submitted frames together, before anything is saved."""
        submitted = [
            form for form in submitted if form.time_frame_subject() is not None
        ]
        if not submitted:
            return

        subjects = {form: form.time_frame_subject() for form in submitted}
        frames = {form: form.time_frame() for form in submitted}
        labels = self._timeline_labels()

        groups: dict[TimeFrameSubjectSiblings, list[forms.Form]] = defaultdict(list)
        for form in submitted:
            groups[subjects[form].sibling_values].append(form)

        for group in groups.values():
            subject = subjects[group[0]]

            for form in group:
                timeline_ids = frames[form].timeline_ids
                if timeline_ids is not None and not timeline_ids <= labels.keys():
                    form.add_error(
                        "timeline_selection",
                        "The timelines must belong to the same global context as "
                        "the time frame's subject.",
                    )

            for form in group:
                for other in group:
                    if form is other:
                        continue
                    form.add_conflict_errors(
                        subjects[other],
                        frames[other],
                        labels,
                        same_subject=(
                            subjects[form].pk is not None
                            and subjects[form].pk == subjects[other].pk
                        ),
                    )

            submitted_ids = {
                subjects[form].pk for form in group if subjects[form].pk is not None
            }
            siblings = subject.siblings().exclude(pk__in=submitted_ids)
            frames_by_subject: dict[int, list[TimeFrameModel]] = defaultdict(list)
            for sibling_frame in (
                subject.sibling_time_frames()
                .exclude(subject_id__in=submitted_ids)
                .prefetch_related("timelines")
            ):
                frames_by_subject[sibling_frame.subject_id].append(sibling_frame)

            for sibling in siblings:
                for form in group:
                    for sibling_frame in frames_by_subject.get(sibling.pk) or [None]:
                        form.add_conflict_errors(
                            sibling, sibling_frame, labels, same_subject=False
                        )

    def clean(self):
        super().clean()
        self.validate_time_frames(
            [
                form
                for form in self.forms
                if form.is_valid() and not form.cleaned_data.get("DELETE")
            ]
        )


class TimeFrameInline(CurrentSettingsInlineMixin, admin.TabularInline):
    form = TimeFrameInlineForm
    formset = TimeFrameInlineFormSet
    extra = 0
    fields = ("valid_from", "valid_to", "timeline_selection")
