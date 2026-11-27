import pytest
from common.models.timeline import TimelineMap, VirtualTimeline


def test_map_ctor():
    sut = TimelineMap()

    assert len(sut) == 0


@pytest.mark.parametrize("timeline", [1, VirtualTimeline(id=1)])
def test_assign_valid_timeline(timeline):
    expected = "expected"
    sut = TimelineMap()

    sut[timeline] = expected

    assert len(sut) == 1
    assert sut[timeline] == expected


def test_key_of_invalid_type():
    sut = TimelineMap()
    with pytest.raises(TypeError) as err_proxy:
        sut["kdsn"] = "error"

    assert str(err_proxy.value) == "unsupported timeline type: 'str'"


def test_all_key(monkeypatch):
    monkeypatch.setattr("common.models.timeline.TimelineMap.ALL_TIMELINES", "*")
    sut = TimelineMap()
    sut[None] = "expected"

    assert len(sut) == 1
    assert sut[None] == "expected"
    assert sut.ALL_TIMELINES == "*"
