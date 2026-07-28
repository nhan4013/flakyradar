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
