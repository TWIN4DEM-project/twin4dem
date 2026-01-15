from unittest.mock import MagicMock, patch

import pytest
from channels.layers import BaseChannelLayer

from simulator.config import ParliamentConfig, CouncilConfig


@pytest.fixture
def legislative_config_deprecated(load_json):
    return load_json("legislative.json")


@pytest.fixture
def judiciary_config_deprecated(load_json):
    return load_json("judiciary.json")


@pytest.fixture
def judiciary_config(judiciary_config_deprecated):
    return CouncilConfig.model_validate(judiciary_config_deprecated)


@pytest.fixture
def parliament_config(legislative_config_deprecated):
    return ParliamentConfig.model_validate(legislative_config_deprecated)


@pytest.fixture
def channel_layer():
    mock = MagicMock(name="mock channel layer", spec=BaseChannelLayer)
    with patch("simulator.tasks.get_channel_layer", return_value=mock):
        yield mock
