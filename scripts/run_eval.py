#!/usr/bin/env python
"""Run the FlakyRadar eval harness and print a report.

Usage: PYTHONPATH=packages python scripts/run_eval.py
Classifier eval needs ANTHROPIC_API_KEY; the retrieval eval runs offline.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "packages"))

from core import eval as eval_mod
from core.eval_data import FLAKY_SAMPLES
from core.retrieval import Candidate


def retrieval_cases():
    """Synthetic RAG retrieval cases: a query embedding near one known-good fix,
    far from unrelated ones, verifying hybrid_rank surfaces the right fix first."""
    race_fix = Candidate(
        id=1,
        text="fixed by adding a lock around charge card to prevent race condition",
        embedding=[1.0, 0.0, 0.0],
    )
    timing_fix = Candidate(
        id=2,
        text="fixed by raising the wait for element timeout threshold",
        embedding=[0.0, 1.0, 0.0],
    )
    network_fix = Candidate(
        id=3,
        text="fixed by mocking the http api client used in tests",
        embedding=[0.0, 0.0, 1.0],
    )
    candidates = [race_fix, timing_fix, network_fix]

    return [
        (
            "threads racing on charge card causes race condition balance mismatch",
            [0.9, 0.1, 0.0],
            candidates,
            {1},
        ),
        (
            "timeout waiting for element modal to close too slow",
            [0.1, 0.9, 0.0],
            candidates,
            {2},
        ),
        (
            "connection error calling external http api",
            [0.0, 0.1, 0.9],
            candidates,
            {3},
        ),
    ]


def main():
    print("## FlakyRadar eval report\n")

    classifier_result = eval_mod.evaluate_classifier(FLAKY_SAMPLES)
    if classifier_result is None:
        print("- classifier: skipped (ANTHROPIC_API_KEY not set)")
    else:
        print(
            f"- classifier: accuracy={classifier_result['accuracy']:.2f} "
            f"macro_f1={classifier_result['macro_f1']:.2f} n={classifier_result['n']}"
        )

    retrieval_result = eval_mod.precision_at_k(retrieval_cases(), k=1)
    print(
        f"- retrieval: precision@{retrieval_result['k']}="
        f"{retrieval_result['precision_at_k']:.2f} n={retrieval_result['n']}"
    )


if __name__ == "__main__":
    main()
