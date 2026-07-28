"""Flakiness scoring: flip detection per commit + Wilson score interval.

A test is flaky when the same commit produces both pass and fail. We count
commits with >=2 runs as "opportunities" and commits with mixed outcomes as
"flips", then estimate the flip probability with a Wilson score interval so
tests with few observations don't outrank well-observed ones.
"""

import math
from collections import defaultdict
from dataclasses import dataclass

FAILING = {"failed", "error"}
# ponytail: fixed window of most recent results; add time-decay weighting if old data dominates
WINDOW = 500


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion. Returns (low, high)."""
    if n <= 0:
        return (0.0, 0.0)
    p = successes / n
    z2 = z * z
    denom = 1 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


@dataclass
class ScoreResult:
    probability: float  # point estimate of flip rate
    ci_low: float
    ci_high: float
    flip_commits: int
    observed_commits: int
    fail_count: int
    run_count: int
    avg_duration: float
    impact: float


def compute_score(observations: list[tuple[str, str, float]]) -> ScoreResult:
    """observations: list of (commit_sha, outcome, duration), skipped excluded by caller or here."""
    by_commit: dict[str, set[str]] = defaultdict(set)
    durations: list[float] = []
    fail_count = 0
    run_count = 0
    for sha, outcome, duration in observations:
        if outcome == "skipped":
            continue
        run_count += 1
        durations.append(duration)
        is_fail = outcome in FAILING
        fail_count += 1 if is_fail else 0
        by_commit[sha].add("fail" if is_fail else "pass")

    # opportunity = commit where a flip was observable (>=2 results… approximated by
    # "commit seen at least twice"); flip = commit with both outcomes
    seen_counts: dict[str, int] = defaultdict(int)
    for sha, outcome, _ in observations:
        if outcome != "skipped":
            seen_counts[sha] += 1
    opportunities = [sha for sha, c in seen_counts.items() if c >= 2]
    flips = [sha for sha in opportunities if len(by_commit[sha]) == 2]

    n_opp = len(opportunities)
    n_flip = len(flips)
    probability = n_flip / n_opp if n_opp else 0.0
    ci_low, ci_high = wilson_interval(n_flip, n_opp)
    avg_duration = sum(durations) / len(durations) if durations else 0.0
    # impact: how much time this test's flakiness burns — flip rate x cost per run x failures seen
    impact = probability * avg_duration * fail_count
    return ScoreResult(
        probability=probability,
        ci_low=ci_low,
        ci_high=ci_high,
        flip_commits=n_flip,
        observed_commits=n_opp,
        fail_count=fail_count,
        run_count=run_count,
        avg_duration=avg_duration,
        impact=impact,
    )
