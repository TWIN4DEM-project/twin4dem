from datetime import datetime

from common.models import AggrandisementBatch


def unsaved_batch(file_name=None, id_=47) -> AggrandisementBatch:
    return AggrandisementBatch(
        id=id_,
        file_name=file_name,
        start_date=datetime(2025, 1, 1),
        end_date=datetime(2025, 12, 31),
    )


def test_batch_str_prefers_the_file_name():
    assert str(unsaved_batch("sample.zip")) == "sample.zip [2025-01-01 → 2025-12-31]"


def test_batch_str_falls_back_to_the_id():
    assert str(unsaved_batch()) == "[id=000047, 2025-01-01 → 2025-12-31]"
