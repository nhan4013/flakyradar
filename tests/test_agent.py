from types import SimpleNamespace

from core import agent


def _text_block(text):
    return SimpleNamespace(type="text", text=text)


def _tool_use_block(name, tool_input, call_id="tool_1"):
    return SimpleNamespace(type="tool_use", name=name, input=tool_input, id=call_id)


def _usage(tokens=100):
    return SimpleNamespace(input_tokens=tokens, output_tokens=tokens)


def test_agent_calls_tool_then_reports_diagnosis(tmp_path, monkeypatch):
    responses = iter(
        [
            SimpleNamespace(
                content=[_tool_use_block("rerun_test", {"n": 5})],
                usage=_usage(),
            ),
            SimpleNamespace(
                content=[
                    _tool_use_block(
                        "report_diagnosis",
                        {
                            "category": "timing_flakiness",
                            "confidence": 0.9,
                            "explanation": "sleep-based wait",
                            "reproduced": True,
                            "evidence": ["3/5 reruns failed"],
                        },
                        call_id="tool_2",
                    )
                ],
                usage=_usage(),
            ),
        ]
    )

    class FakeMessages:
        def create(self, **kwargs):
            return next(responses)

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(agent, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(agent.agent_tools, "rerun_test", lambda *a, **k: "3/5 passed, 2/5 failed")

    report, steps = agent.run_diagnostic_agent(
        "img", tmp_path, tmp_path, "tests.test_foo::test_bar", "trace", "msg"
    )

    assert report["category"] == "timing_flakiness"
    assert report["reproduced"] is True
    assert len(steps) == 2
    assert steps[0]["tool"] == "rerun_test"
    assert steps[1]["tool"] == "report_diagnosis"


def test_agent_stops_at_step_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "MAX_STEPS", 2)

    def always_rerun(**kwargs):
        return SimpleNamespace(content=[_tool_use_block("rerun_test", {"n": 1})], usage=_usage())

    class FakeMessages:
        def create(self, **kwargs):
            return always_rerun(**kwargs)

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(agent, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(agent.agent_tools, "rerun_test", lambda *a, **k: "1/1 passed")

    report, steps = agent.run_diagnostic_agent(
        "img", tmp_path, tmp_path, "tests.test_foo::test_bar", "trace", "msg"
    )

    assert report["category"] == "unknown"
    assert "budget" in report["explanation"]
    assert len(steps) == 2


def test_agent_stops_at_token_budget(tmp_path, monkeypatch):
    monkeypatch.setattr(agent, "MAX_TOKENS_BUDGET", 50)

    def always_rerun(**kwargs):
        return SimpleNamespace(content=[_tool_use_block("rerun_test", {"n": 1})], usage=_usage(tokens=30))

    class FakeMessages:
        def create(self, **kwargs):
            return always_rerun(**kwargs)

    class FakeClient:
        messages = FakeMessages()

    monkeypatch.setattr(agent, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(agent.agent_tools, "rerun_test", lambda *a, **k: "1/1 passed")

    report, steps = agent.run_diagnostic_agent(
        "img", tmp_path, tmp_path, "tests.test_foo::test_bar", "trace", "msg"
    )

    assert "token budget" in report["explanation"]
    assert len(steps) == 1


def test_tool_exception_surfaces_as_error_string(tmp_path, monkeypatch):
    monkeypatch.setattr(
        agent.agent_tools,
        "rerun_test",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("sandbox exploded")),
    )
    output = agent._execute_tool("rerun_test", {"n": 1}, "img", tmp_path, tmp_path, "t::x")
    assert output.startswith("error:")
    assert "sandbox exploded" in output
