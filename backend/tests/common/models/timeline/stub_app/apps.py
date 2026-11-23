from django.apps import AppConfig


class TimelineTestsConfig(AppConfig):
    default_auto_field = "django.db.models.AutoField"
    name = "tests.common.models.timeline.stub_app"
    label = "timeline_tests"
