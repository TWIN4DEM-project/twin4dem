import pytest
from channels.layers import get_channel_layer


@pytest.fixture
def channel_layer():
    return get_channel_layer("default")
