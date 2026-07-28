"""Hand-curated seed dataset for the classifier eval harness.

Small stand-in for a public labeled flaky-test dataset (e.g. FlakeFlagger) — not
mined data. Swap in a real labeled dataset before citing these numbers as a public
benchmark; see plan.md Phase 4.
"""

# (test_id, stack_trace, failure_message, true_category)
FLAKY_SAMPLES = [
    (
        "tests/test_orders.py::test_concurrent_checkout",
        (
            "Thread-1 charge_card()\nThread-2 charge_card()\n"
            "AssertionError: balance mismatch, expected one charge"
        ),
        "AssertionError: expected balance 100, got 80",
        "race_condition",
    ),
    (
        "tests/test_cache.py::test_shared_counter",
        "counter += 1  # module-level global, mutated by test_increment_counter",
        "AssertionError: expected counter == 1, got 3",
        "test_order_dependency",
    ),
    (
        "tests/test_ui.py::test_modal_closes",
        "wait_for_element(timeout=0.1)\nTimeoutError: element .modal not visible",
        "TimeoutError: modal did not close within 100ms",
        "timing_flakiness",
    ),
    (
        "tests/test_api_client.py::test_fetch_user",
        (
            "requests.get('https://api.example.com/user/1')\n"
            "ConnectionError: Failed to establish a new connection"
        ),
        "requests.exceptions.ConnectionError: Connection refused",
        "network",
    ),
    (
        "tests/test_db_pool.py::test_query_after_many_inserts",
        (
            "psycopg.OperationalError: too many connections for role\n"
            "conn = pool.getconn()  # never returned by a prior test"
        ),
        "OperationalError: FATAL: too many connections",
        "resource_leak",
    ),
    (
        "tests/test_render.py::test_random_layout",
        "assert layout.width > 0\nAssertionError",
        "AssertionError: assert -3 > 0",
        "unknown",
    ),
    (
        "tests/test_locks.py::test_two_writers",
        (
            "with file_lock:\n    write_data()\nAssertionError: data corrupted, "
            "two writers held the lock simultaneously"
        ),
        "AssertionError: data corrupted by concurrent write",
        "race_condition",
    ),
    (
        "tests/test_suite_state.py::test_needs_seeded_db",
        "KeyError: 'seed_user'  # fixture only populated by an earlier test in the suite",
        "KeyError: 'seed_user' not found",
        "test_order_dependency",
    ),
]
