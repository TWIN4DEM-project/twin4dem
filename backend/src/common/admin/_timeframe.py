import copy
from collections import defaultdict
from dataclasses import dataclass

from django import forms
from django.contrib import admin

from ..models import FrameSpec, TimeFrameSubject, VirtualTimeline
from ..models.timeline import TimeFrameSubjectSiblings


@dataclass(frozen=True)
class TimeFrameCandidate:
    """An in-memory frame candidate submitted through an admin inline."""

    form: forms.Form
    subject: TimeFrameSubject
    spec: FrameSpec


def _timeline_labels(subject: TimeFrameSubject) -> dict[int, str]:
    """The timelines of the subject's global context, by id and label."""
    return dict(
        VirtualTimeline.objects.filter(
            user_settings_id=subject.time_frame_user_settings_id()
        ).values_list("id", "label")
    )


def _same_subject(first: TimeFrameCandidate, second: TimeFrameCandidate) -> bool:
    if first.subject is second.subject:
        return True
    return (
        first.subject.pk is not None
        and second.subject.pk is not None
        and first.subject.pk == second.subject.pk
    )


def _add_conflict_errors(
    candidate: TimeFrameCandidate,
    other_subject: TimeFrameSubject,
    other_spec: FrameSpec,
    labels: dict[int, str],
    *,
    same_subject: bool,
) -> None:
    if not candidate.spec.shares_timeline_with(other_spec):
        return

    if same_subject:
        candidate.form.add_error(
            None,
            f"{candidate.subject.time_frame_label()} already occupies the time "
            f"frame {other_spec.format_interval()} on "
            f"{candidate.spec.format_timelines(other_spec, labels)}.",
        )
        return

    if not candidate.spec.overlaps_in_time(other_spec):
        return

    if other_spec == FrameSpec(None, None, None):
        candidate.form.add_error(
            None,
            f"{other_subject.time_frame_label()} has no time frame, so it is "
            f"active at all times on all timelines.",
        )
        return

    candidate.form.add_error(
        None,
        f"Overlaps with {other_subject.time_frame_label()} "
        f"{other_spec.format_interval()} on "
        f"{candidate.spec.format_timelines(other_spec, labels)}.",
    )


def timeline_selection_field() -> forms.ModelMultipleChoiceField:
    # not the `timelines` model field: the frame must be validated together with
    # its timelines, before anything is saved
    return forms.ModelMultipleChoiceField(
        queryset=VirtualTimeline.objects.select_related("user_settings"),
        required=False,
        label="Timelines",
        help_text="Leave empty to apply the time frame to all timelines.",
    )


class TimelineSelectionFormMixin:
    # restricts the selectable timelines; set per request by the inline
    timeline_queryset = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.timeline_queryset is not None:
            self.fields["timeline_selection"].queryset = self.timeline_queryset
        frame = self.frame_to_edit()
        if frame is not None and frame.pk is not None:
            self.initial["timeline_selection"] = frame.timelines.all()

    def frame_to_edit(self):
        return self.instance

    def time_frame_subject(self) -> TimeFrameSubject | None:
        return getattr(self.instance, "subject", None)

    def time_frame_spec(self) -> FrameSpec:
        timeline_ids = self.selected_timeline_ids()
        return FrameSpec(
            self.cleaned_data.get("valid_from"),
            self.cleaned_data.get("valid_to"),
            None if timeline_ids is None else frozenset(timeline_ids),
        )

    def time_frame_candidate(self) -> TimeFrameCandidate | None:
        subject = self.time_frame_subject()
        if subject is None:
            return None
        return TimeFrameCandidate(
            form=self, subject=subject, spec=self.time_frame_spec()
        )

    def selected_timelines(self) -> list[VirtualTimeline]:
        return list(self.cleaned_data.get("timeline_selection") or ())

    def selected_timeline_ids(self) -> list[int] | None:
        return [timeline.pk for timeline in self.selected_timelines()] or None


class TimelineQuerysetInlineMixin:
    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj, **kwargs)
        if request.user.is_superuser:
            return formset
        base_form = formset.form
        form = type(base_form.__name__, (base_form,), {})
        form.base_fields = base_form.base_fields.copy()
        field = copy.copy(form.base_fields["timeline_selection"])
        field.queryset = VirtualTimeline.objects.filter(
            user_settings__user=request.user
        )
        form.base_fields["timeline_selection"] = field
        formset.form = form
        return formset


class TimeFrameInlineForm(TimelineSelectionFormMixin, forms.ModelForm):
    timeline_selection = timeline_selection_field()

    class Meta:
        fields = ("valid_from", "valid_to")

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
    @staticmethod
    def validate_time_frame_candidates(candidates: list[TimeFrameCandidate]) -> None:
        """Validate candidate frames together, before anything is saved."""
        if not candidates:
            return

        groups: dict[TimeFrameSubjectSiblings, list[TimeFrameCandidate]] = defaultdict(
            list
        )
        for candidate in candidates:
            groups[candidate.subject.sibling_values].append(candidate)

        for group in groups.values():
            labels = _timeline_labels(group[0].subject)
            for candidate in group:
                timeline_ids = candidate.spec.timeline_ids
                if timeline_ids is not None and not timeline_ids <= labels.keys():
                    candidate.form.add_error(
                        "timeline_selection",
                        "The timelines must belong to the same global context as "
                        "the time frame's subject.",
                    )

            for candidate in group:
                for other in group:
                    if candidate is other:
                        continue
                    _add_conflict_errors(
                        candidate,
                        other.subject,
                        other.spec,
                        labels,
                        same_subject=_same_subject(candidate, other),
                    )

            subject = group[0].subject
            candidate_subject_ids = {
                candidate.subject.pk
                for candidate in group
                if candidate.subject.pk is not None
            }
            siblings = subject.siblings().exclude(pk__in=candidate_subject_ids)
            frames_by_subject: dict[int, list[FrameSpec]] = defaultdict(list)
            sibling_frames = subject.sibling_time_frames().exclude(
                subject_id__in=candidate_subject_ids
            )
            for frame in sibling_frames:
                frames_by_subject[frame.subject_id].append(frame.spec)
            for sibling in siblings:
                for candidate in group:
                    for spec in frames_by_subject.get(sibling.pk, []) or [
                        FrameSpec(None, None, None)
                    ]:
                        _add_conflict_errors(
                            candidate,
                            sibling,
                            spec,
                            labels,
                            same_subject=False,
                        )

    def clean(self):
        super().clean()
        candidates = [
            form.time_frame_candidate()
            for form in self.forms
            if form.is_valid() and not form.cleaned_data.get("DELETE")
        ]
        self.validate_time_frame_candidates(candidates)


class TimeFrameInline(TimelineQuerysetInlineMixin, admin.TabularInline):
    form = TimeFrameInlineForm
    formset = TimeFrameInlineFormSet
    extra = 0
    fields = ("valid_from", "valid_to", "timeline_selection")
