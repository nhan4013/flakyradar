import pytest
from core.models import FlakinessScore, Project, TestResult, TestRun

XML_PASS = """<testsuite><testcase classname="t" name="x" time="0.1"/></testsuite>"""
XML_FAIL = """<testsuite><testcase classname="t" name="x" time="0.1">
<failure message="boom">trace</failure></testcase></testsuite>"""


@pytest.mark.django_db
def test_ingest_report_creates_run_and_results():
    from core.services import ingest_report

    project = Project.objects.create(name="Demo", slug="demo")
    run = ingest_report(project.id, "sha1", "main", "ci-1", XML_PASS)
    assert TestRun.objects.filter(pk=run.pk).exists()
    assert TestResult.objects.filter(run=run).count() == 1


@pytest.mark.django_db
def test_recompute_score_detects_flip_across_two_ingests():
    from core.services import ingest_report

    project = Project.objects.create(name="Demo", slug="demo")
    ingest_report(project.id, "sha-flip", "main", "ci-1", XML_PASS)
    ingest_report(project.id, "sha-flip", "main", "ci-2", XML_FAIL)

    score = FlakinessScore.objects.get(case__test_id="t::x")
    assert score.flip_commits == 1
    assert score.observed_commits == 1
    assert score.probability == 1.0


@pytest.mark.django_db
def test_analyze_project_skips_without_ai_keys(monkeypatch):
    from core.services import analyze_project

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("VOYAGE_API_KEY", raising=False)
    project = Project.objects.create(name="Demo", slug="demo")
    result = analyze_project(project.id)
    assert "skipped" in result


@pytest.mark.django_db
def test_analyze_project_clusters_and_diagnoses(monkeypatch):
    from core.models import Diagnosis, FailureCluster
    from core.services import analyze_project, ingest_report

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setattr(
        "core.services.embeddings.embed_texts",
        lambda texts: [[1.0, 0.0] for _ in texts],
    )
    monkeypatch.setattr(
        "core.services.llm.classify_root_cause",
        lambda test_id, stack_trace, message: {
            "category": "timing_flakiness",
            "confidence": 0.8,
            "explanation": "flaky due to sleep",
            "suggested_fix": "remove sleep, use polling",
        },
    )

    project = Project.objects.create(name="Demo", slug="demo")
    ingest_report(project.id, "sha1", "main", "ci-1", XML_FAIL)
    ingest_report(project.id, "sha2", "main", "ci-2", XML_FAIL)

    result = analyze_project(project.id)
    assert result["clusters"] == 1
    cluster = FailureCluster.objects.get()
    assert cluster.size == 2
    diagnosis = Diagnosis.objects.get(cluster=cluster)
    assert diagnosis.category == "timing_flakiness"
    assert diagnosis.confidence == 0.8
    assert diagnosis.rag_suggestion == ""
    assert diagnosis.evidence == []


@pytest.mark.django_db
def test_analyze_project_finds_similar_past_fix(monkeypatch):
    from core.models import Diagnosis, FailureCluster, FixRecord, TestCase
    from core.services import analyze_project, ingest_report

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
    monkeypatch.setattr(
        "core.services.embeddings.embed_texts",
        lambda texts: [[1.0, 0.0] for _ in texts],
    )
    monkeypatch.setattr(
        "core.services.llm.classify_root_cause",
        lambda test_id, stack_trace, message: {
            "category": "timing_flakiness",
            "confidence": 0.8,
            "explanation": "flaky due to sleep",
            "suggested_fix": "remove sleep, use polling",
        },
    )
    monkeypatch.setattr(
        "core.services.llm.suggest_fix",
        lambda test_id, stack_trace, message, similar_fixes: {
            "suggestion": f"same as commit {similar_fixes[0]['commit_sha']}",
            "confidence": 0.9,
        },
    )

    project = Project.objects.create(name="Demo", slug="demo")

    # a prior, already-resolved cluster with the same centroid direction
    old_case = TestCase.objects.create(project=project, test_id="t::old")
    old_run = TestRun.objects.create(project=project, commit_sha="sha-old", branch="main")
    old_result = TestResult.objects.create(
        run=old_run,
        case=old_case,
        outcome="failed",
        message="boom",
        stack_trace="trace",
        embedding=[1.0, 0.0],
    )
    old_cluster = FailureCluster.objects.create(
        project=project, representative=old_result, centroid=[1.0, 0.0], size=1
    )
    FixRecord.objects.create(cluster=old_cluster, commit_sha="abc123", description="added a lock")

    ingest_report(project.id, "sha1", "main", "ci-1", XML_FAIL)
    ingest_report(project.id, "sha2", "main", "ci-2", XML_FAIL)
    analyze_project(project.id)

    new_cluster = FailureCluster.objects.exclude(pk=old_cluster.pk).get()
    diagnosis = Diagnosis.objects.get(cluster=new_cluster)
    assert diagnosis.rag_suggestion == "same as commit abc123"
    assert diagnosis.evidence[0]["commit_sha"] == "abc123"
