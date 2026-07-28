from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import (
    AgentRun,
    FailureCluster,
    FlakinessScore,
    QuarantineEntry,
    TestCase,
    TestResult,
)


def index(request):
    scores = (
        FlakinessScore.objects.filter(probability__gt=0)
        .select_related("case", "case__project")
        .annotate(
            quarantined=Exists(
                QuarantineEntry.objects.filter(case=OuterRef("case"), active=True)
            )
        )
        .order_by("-impact", "-probability")[:200]
    )
    return render(request, "core/index.html", {"scores": scores})


def test_detail(request, case_id: int):
    case = get_object_or_404(TestCase.objects.select_related("project"), pk=case_id)
    results = (
        TestResult.objects.filter(case=case)
        .select_related("run")
        .order_by("-run__created_at", "-id")[:100]
    )
    score = FlakinessScore.objects.filter(case=case).first()
    quarantined = QuarantineEntry.objects.filter(case=case, active=True).exists()
    latest_failure = (
        TestResult.objects.filter(case=case, outcome__in=["failed", "error"])
        .exclude(cluster=None)
        .select_related("cluster__diagnosis")
        .order_by("-run__created_at", "-id")
        .first()
    )
    diagnosis = getattr(latest_failure.cluster, "diagnosis", None) if latest_failure else None
    cluster = latest_failure.cluster if latest_failure else None
    agent_runs = AgentRun.objects.filter(cluster=cluster).order_by("-started_at") if cluster else []
    return render(
        request,
        "core/test_detail.html",
        {
            "case": case,
            "results": results,
            "score": score,
            "quarantined": quarantined,
            "diagnosis": diagnosis,
            "cluster": cluster,
            "agent_runs": agent_runs,
        },
    )


@require_POST
def toggle_quarantine(request, case_id: int):
    case = get_object_or_404(TestCase, pk=case_id)
    active = QuarantineEntry.objects.filter(case=case, active=True)
    if active.exists():
        active.update(active=False)
    else:
        QuarantineEntry.objects.create(case=case, reason=request.POST.get("reason", ""))
    return redirect("test_detail", case_id=case.pk)


@require_POST
def trigger_diagnosis(request, cluster_id: int):
    from worker.tasks import diagnose

    cluster = get_object_or_404(FailureCluster, pk=cluster_id)
    diagnose.delay(cluster_id)
    return redirect("test_detail", case_id=cluster.representative.case_id)


def agent_run_detail(request, run_id: int):
    run = get_object_or_404(
        AgentRun.objects.select_related("cluster", "cluster__representative__case"), pk=run_id
    )
    steps = run.steps.all()
    return render(request, "core/agent_run_detail.html", {"run": run, "steps": steps})
