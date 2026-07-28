"""Ingest + scoring pipeline. Called from Celery tasks; DB logic lives here so tests hit it directly."""

from core import scoring
from core.junit import parse_junit_xml
from core.models import FlakinessScore, Project, TestCase, TestResult, TestRun


def ingest_report(
    project_id: int, commit_sha: str, branch: str, ci_run_id: str, xml_text: str
) -> TestRun:
    project = Project.objects.get(pk=project_id)
    parsed = parse_junit_xml(xml_text)
    run = TestRun.objects.create(
        project=project, commit_sha=commit_sha, branch=branch, ci_run_id=ci_run_id
    )
    results = []
    touched_cases = []
    for item in parsed:
        case, _ = TestCase.objects.get_or_create(project=project, test_id=item.test_id)
        touched_cases.append(case)
        results.append(
            TestResult(
                run=run,
                case=case,
                outcome=item.outcome,
                duration=item.duration,
                message=item.message[:2000],
                stack_trace=item.stack_trace,
            )
        )
    TestResult.objects.bulk_create(results)
    for case in touched_cases:
        recompute_case_score(case)
    return run


def recompute_case_score(case: TestCase) -> FlakinessScore:
    rows = (
        TestResult.objects.filter(case=case)
        .select_related("run")
        .order_by("-run__created_at", "-id")[: scoring.WINDOW]
    )
    observations = [(r.run.commit_sha, r.outcome, r.duration) for r in rows]
    s = scoring.compute_score(observations)
    score, _ = FlakinessScore.objects.update_or_create(
        case=case,
        defaults={
            "probability": s.probability,
            "ci_low": s.ci_low,
            "ci_high": s.ci_high,
            "flip_commits": s.flip_commits,
            "observed_commits": s.observed_commits,
            "fail_count": s.fail_count,
            "run_count": s.run_count,
            "avg_duration": s.avg_duration,
            "impact": s.impact,
        },
    )
    return score
