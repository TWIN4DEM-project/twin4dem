from unittest.mock import MagicMock, call

import pytest
from celery import chain

from simulator.tasks import (
    decide_and_dispatch,
    send_result_to_channel,
    subsequent_submodel,
)


@pytest.fixture
def replace_mock(monkeypatch):
    mock = MagicMock(
        name="replace_mock", spec=decide_and_dispatch.replace, return_value=None
    )
    monkeypatch.setattr(decide_and_dispatch, "replace", mock)
    return mock


def test_aggrandisement_not_approved_return_send_result_to_channel(
    executive_submodel_output, replace_mock
):
    task = chain(
        decide_and_dispatch.s(
            step_result=executive_submodel_output, channel_name="test-channel"
        )
    )
    task.apply_async().get()

    assert replace_mock.call_args_list == [
        call(send_result_to_channel.s(executive_submodel_output, "test-channel"))
    ]


@pytest.mark.parametrize("approved", [True], indirect=True)
def test_aggrandisement_approved_return_chain(executive_submodel_output, replace_mock):
    task = chain(
        decide_and_dispatch.s(
            step_result=executive_submodel_output, channel_name="test-channel"
        )
    )
    task.apply_async().get()

    assert replace_mock.call_args_list == [
        call(
            chain(
                subsequent_submodel.s(executive_submodel_output),
                send_result_to_channel.s("test-channel"),
            )
        )
    ]
