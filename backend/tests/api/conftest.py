import pytest


@pytest.fixture(scope="session")
def aggrandisement_batch_dirname():
    return "aggrandisement-batches"


@pytest.fixture
def aggrandisement_batch_name(request):
    return getattr(request, "param", "one-unit.json")


@pytest.fixture
def aggrandisement_batch_path(
    request, data_dir, aggrandisement_batch_dirname, aggrandisement_batch_name
):
    return data_dir / aggrandisement_batch_dirname / aggrandisement_batch_name


@pytest.fixture(scope="session")
def load_batch(aggrandisement_batch_dirname, load_json):
    def _(name: str) -> dict:
        return load_json(f"{aggrandisement_batch_dirname}/{name}")

    return _


@pytest.fixture
def aggrandisement_batch(request, load_batch, aggrandisement_batch_name):
    return load_batch(aggrandisement_batch_name)
