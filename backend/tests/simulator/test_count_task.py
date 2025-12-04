from unittest.mock import patch
from channels.layers import InMemoryChannelLayer

from src.simulator.tasks import count_to_ten
from asgiref.sync import async_to_sync
from typing import Dict, List


def test_count_to_ten_sends_nine_messages():
    channel_name = "test-channel"

    layer = InMemoryChannelLayer()

    with (
        patch("src.simulator.tasks.get_channel_layer", return_value=layer),
        patch("src.simulator.tasks.sleep", return_value=None),
    ):
        count_to_ten.delay(channel_name)

    receive = async_to_sync(layer.receive)

    messages: List[Dict] = []
    for _ in range(1, 10):
        msg = receive(channel_name)
        messages.append(msg)

    # 1 Exactly 9 messages
    assert len(messages) == 9

    # 2 All messages have the expected type
    assert all(m["type"] == "counter.update" for m in messages)

    # 3 Values go 1..9 in order
    assert [m["value"] for m in messages] == list(range(1, 10))