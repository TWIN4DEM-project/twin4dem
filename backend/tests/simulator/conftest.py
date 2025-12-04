import pytest

@pytest.fixture(autouse=True)
def celery_eager(settings):
    """
    Make Celery tasks execute synchronously in tests.
    That way .delay().get() just runs the function directly.
    """
    settings.CELERY_TASK_ALWAYS_EAGER = True
    settings.CELERY_TASK_EAGER_PROPAGATES = True