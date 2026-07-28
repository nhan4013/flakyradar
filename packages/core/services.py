"""Ingest + scoring pipeline. Called from Celery tasks; DB logic lives here so tests hit it directly."""

import os

from core import clustering, embeddings, llm, retrieval, scoring
from core.junit import parse_junit_xml
from core.models import (
    Diagnosis,
    FailureCluster,
    FixRecord,
    FlakinessScore,
    Project,
    TestCase,
    TestResult,
    TestRun,
)


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


def analyze_project(project_id: int, window: int = 500) -> dict:
    """Embed recent failures, cluster duplicates, and classify root cause per cluster.

    No-ops when ANTHROPIC_API_KEY / VOYAGE_API_KEY aren't set, so ingest+scoring
    keeps working without AI keys configured.
    """
    if not os.environ.get("ANTHROPIC_API_KEY") or not os.environ.get("VOYAGE_API_KEY"):
        return {"skipped": "missing ANTHROPIC_API_KEY or VOYAGE_API_KEY"}

    project = Project.objects.get(pk=project_id)
    failing = list(
        TestResult.objects.filter(run__project=project, outcome__in=["failed", "error"])
        .exclude(stack_trace="")
        .select_related("case", "run")
        .order_by("-run__created_at")[:window]
    )
    if not failing:
        return {"clusters": 0}

    to_embed = [r for r in failing if not r.embedding]
    if to_embed:
        texts = [f"{r.message}\n{r.stack_trace}" for r in to_embed]
        vectors = embeddings.embed_texts(texts)
        for r, vec in zip(to_embed, vectors, strict=True):
            r.embedding = vec
        TestResult.objects.bulk_update(to_embed, ["embedding"])

    embedded = [r for r in failing if r.embedding]
    labels = clustering.cluster_embeddings([r.embedding for r in embedded])

    groups: dict[int, list[TestResult]] = {}
    for r, label in zip(embedded, labels, strict=True):
        if label != -1:
            groups.setdefault(label, []).append(r)

    # ponytail: each run creates fresh clusters rather than merging with prior ones —
    # add centroid-similarity matching across runs if duplicate clusters pile up
    for members in groups.values():
        vectors = [m.embedding for m in members]
        centroid = [sum(vals) / len(vals) for vals in zip(*vectors, strict=True)]
        representative = members[0]
        cluster = FailureCluster.objects.create(
            project=project, representative=representative, centroid=centroid, size=len(members)
        )
        TestResult.objects.filter(pk__in=[m.pk for m in members]).update(cluster=cluster)
        result = llm.classify_root_cause(
            representative.case.test_id, representative.stack_trace, representative.message
        )

        similar = find_similar_fixes(
            project, f"{representative.message}\n{representative.stack_trace}", centroid
        )
        rag = llm.suggest_fix(
            representative.case.test_id,
            representative.stack_trace,
            representative.message,
            [{"commit_sha": fr.commit_sha, "description": fr.description} for fr, _ in similar],
        )

        Diagnosis.objects.create(
            cluster=cluster,
            category=result["category"],
            confidence=result["confidence"],
            explanation=result["explanation"],
            suggested_fix=result["suggested_fix"],
            rag_suggestion=rag["suggestion"],
            evidence=[
                {
                    "fix_record_id": fr.id,
                    "commit_sha": fr.commit_sha,
                    "description": fr.description,
                    "score": score,
                }
                for fr, score in similar
            ],
        )
    return {"clusters": len(groups)}


def find_similar_fixes(
    project: Project, query_text: str, query_embedding: list[float], k: int = 3
) -> list[tuple[FixRecord, float]]:
    """RAG retrieval: find past-resolved clusters whose fix might apply here."""
    resolved = FixRecord.objects.filter(cluster__project=project).select_related(
        "cluster", "cluster__representative"
    )
    candidates = []
    fix_by_id = {}
    for fr in resolved:
        if fr.cluster.representative is None:
            continue
        candidates.append(
            retrieval.Candidate(
                id=fr.id,
                text=f"{fr.description}\n{fr.cluster.representative.message}",
                embedding=fr.cluster.centroid,
            )
        )
        fix_by_id[fr.id] = fr
    ranked = retrieval.hybrid_rank(query_text, query_embedding, candidates, k=k)
    return [(fix_by_id[c.id], score) for c, score in ranked]
