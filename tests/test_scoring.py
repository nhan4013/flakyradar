from core import scoring


def test_no_flip_when_always_passing():
    obs = [("c1", "passed", 1.0), ("c2", "passed", 1.0), ("c2", "passed", 1.0)]
    r = scoring.compute_score(obs)
    assert r.observed_commits == 1  # only c2 seen twice
    assert r.flip_commits == 0
    assert r.probability == 0.0


def test_flip_detected_within_same_commit():
    obs = [
        ("c1", "passed", 1.0),
        ("c1", "failed", 1.0),
        ("c2", "passed", 1.0),
        ("c2", "passed", 1.0),
    ]
    r = scoring.compute_score(obs)
    assert r.observed_commits == 2
    assert r.flip_commits == 1
    assert r.probability == 0.5


def test_single_run_commit_is_not_an_opportunity():
    obs = [("c1", "passed", 1.0), ("c2", "failed", 1.0)]
    r = scoring.compute_score(obs)
    assert r.observed_commits == 0
    assert r.probability == 0.0


def test_skipped_excluded_from_run_count():
    obs = [("c1", "passed", 1.0), ("c1", "skipped", 0.0)]
    r = scoring.compute_score(obs)
    assert r.run_count == 1


def test_wilson_interval_narrows_with_more_data():
    low_n = scoring.wilson_interval(1, 2)
    high_n = scoring.wilson_interval(50, 100)
    assert (low_n[1] - low_n[0]) > (high_n[1] - high_n[0])


def test_wilson_interval_zero_n():
    assert scoring.wilson_interval(0, 0) == (0.0, 0.0)


def test_impact_scales_with_probability_duration_and_failures():
    obs = [
        ("c1", "failed", 10.0),
        ("c1", "passed", 10.0),
        ("c2", "failed", 10.0),
        ("c2", "passed", 10.0),
    ]
    r = scoring.compute_score(obs)
    assert r.impact == r.probability * r.avg_duration * r.fail_count
    assert r.impact > 0
