from django.db.models import Exists, OuterRef
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from core.models import FlakinessScore, QuarantineEntry, TestCase, TestResult


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
    return render(
        request,
        "core/test_detail.html",
        {"case": case, "results": results, "score": score, "quarantined": quarantined},
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
