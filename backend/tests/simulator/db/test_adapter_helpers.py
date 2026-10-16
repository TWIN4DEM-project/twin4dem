from simulator.db._adapter import _random_frequency, _random_gauss


def test_random_gauss_retries_draws_outside_the_bounds(monkeypatch):
    draws = iter([42.0, 0.3])
    monkeypatch.setattr("random.gauss", lambda *a, **k: next(draws))

    assert _random_gauss(0.5, lo=0.0, hi=1.0) == 0.3


def test_random_frequency_is_hi_for_draws_below_the_center(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.1)

    assert _random_frequency(0.5) == 1.0


def test_random_frequency_is_lo_for_draws_from_the_center(monkeypatch):
    monkeypatch.setattr("random.random", lambda: 0.5)

    assert _random_frequency(0.5) == 0.0


def test_effective_probability_prefers_the_institution_override():
    from simulator.db._adapter import _effective

    assert _effective(0.7, 0.2) == 0.7
    assert _effective(None, 0.2) == 0.2
