from api.services._random import random_frequency, random_gauss


def test_random_gauss_retries_draws_outside_the_bounds(monkeypatch):
    draws = iter([42.0, 0.3])
    monkeypatch.setattr("api.services._random.gauss", lambda *a, **k: next(draws))

    assert random_gauss(0.5, lo=0.0, hi=1.0) == 0.3


def test_random_frequency_is_hi_for_draws_below_the_center(monkeypatch):
    monkeypatch.setattr("api.services._random.random", lambda: 0.1)

    assert random_frequency(0.5) == 1.0


def test_random_frequency_is_lo_for_draws_from_the_center(monkeypatch):
    monkeypatch.setattr("api.services._random.random", lambda: 0.5)

    assert random_frequency(0.5) == 0.0
