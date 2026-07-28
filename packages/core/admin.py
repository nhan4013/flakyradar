from django.contrib import admin

from core.models import (
    Diagnosis,
    FailureCluster,
    FixRecord,
    FlakinessScore,
    Project,
    QuarantineEntry,
    TestCase,
    TestResult,
    TestRun,
)


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ("slug", "name", "api_key", "created_at")


@admin.register(TestRun)
class TestRunAdmin(admin.ModelAdmin):
    list_display = ("project", "commit_sha", "branch", "ci_run_id", "created_at")
    list_filter = ("project", "branch")


@admin.register(TestCase)
class TestCaseAdmin(admin.ModelAdmin):
    list_display = ("test_id", "project")
    search_fields = ("test_id",)


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ("case", "run", "outcome", "duration")
    list_filter = ("outcome",)


@admin.register(FlakinessScore)
class FlakinessScoreAdmin(admin.ModelAdmin):
    list_display = ("case", "probability", "ci_low", "ci_high", "impact", "updated_at")


@admin.register(QuarantineEntry)
class QuarantineEntryAdmin(admin.ModelAdmin):
    list_display = ("case", "active", "reason", "created_at")
    list_filter = ("active",)


@admin.register(FailureCluster)
class FailureClusterAdmin(admin.ModelAdmin):
    list_display = ("id", "project", "representative", "size", "created_at")
    list_filter = ("project",)


@admin.register(Diagnosis)
class DiagnosisAdmin(admin.ModelAdmin):
    list_display = ("cluster", "category", "confidence", "created_at")
    list_filter = ("category",)


@admin.register(FixRecord)
class FixRecordAdmin(admin.ModelAdmin):
    list_display = ("cluster", "commit_sha", "created_at")
