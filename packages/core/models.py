import secrets

from django.db import models


def make_api_key() -> str:
    return secrets.token_hex(24)


class Project(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    repo_url = models.URLField(blank=True)
    api_key = models.CharField(max_length=64, unique=True, default=make_api_key)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.slug


class TestRun(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="runs")
    commit_sha = models.CharField(max_length=64)
    branch = models.CharField(max_length=200, default="main")
    ci_run_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["project", "commit_sha"])]

    def __str__(self):
        return f"{self.project.slug}@{self.commit_sha[:8]}"


class TestCase(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="cases")
    # "path/to/file.py::TestClass::test_name" style identifier
    test_id = models.CharField(max_length=500)

    class Meta:
        unique_together = [("project", "test_id")]

    def __str__(self):
        return self.test_id


class TestResult(models.Model):
    class Outcome(models.TextChoices):
        PASSED = "passed"
        FAILED = "failed"
        ERROR = "error"
        SKIPPED = "skipped"

    run = models.ForeignKey(TestRun, on_delete=models.CASCADE, related_name="results")
    case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name="results")
    outcome = models.CharField(max_length=10, choices=Outcome.choices)
    duration = models.FloatField(default=0.0)
    message = models.TextField(blank=True)
    stack_trace = models.TextField(blank=True)
    # ponytail: JSONField list[float] instead of pgvector VectorField — clustering runs
    # in-process over a batch, no DB-side ANN search yet. Upgrade when Phase 2 RAG
    # retrieval needs live nearest-neighbor queries.
    embedding = models.JSONField(null=True, blank=True)
    cluster = models.ForeignKey(
        "FailureCluster", on_delete=models.SET_NULL, null=True, blank=True, related_name="members"
    )

    class Meta:
        indexes = [models.Index(fields=["case", "run"])]


class FailureCluster(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="failure_clusters")
    representative = models.ForeignKey(
        TestResult, on_delete=models.SET_NULL, null=True, related_name="+"
    )
    centroid = models.JSONField()
    size = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class Diagnosis(models.Model):
    class Category(models.TextChoices):
        RACE_CONDITION = "race_condition"
        TEST_ORDER_DEPENDENCY = "test_order_dependency"
        TIMING_FLAKINESS = "timing_flakiness"
        NETWORK = "network"
        RESOURCE_LEAK = "resource_leak"
        UNKNOWN = "unknown"

    cluster = models.OneToOneField(FailureCluster, on_delete=models.CASCADE, related_name="diagnosis")
    category = models.CharField(max_length=30, choices=Category.choices)
    confidence = models.FloatField(default=0.0)
    explanation = models.TextField(blank=True)
    suggested_fix = models.TextField(blank=True)
    # RAG: LLM suggestion grounded in similar past fixes (see FixRecord), plus what was retrieved
    rag_suggestion = models.TextField(blank=True)
    evidence = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class FixRecord(models.Model):
    """Marks a FailureCluster as resolved and how — the knowledge base for RAG retrieval.

    ponytail: created manually via Django Admin for now; auto-detecting the fixing
    commit via the GitHub API is the upgrade path once there's a real repo to mine.
    """

    cluster = models.OneToOneField(FailureCluster, on_delete=models.CASCADE, related_name="fix")
    commit_sha = models.CharField(max_length=64)
    description = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)


class AgentRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running"
        COMPLETED = "completed"
        FAILED = "failed"

    cluster = models.ForeignKey(FailureCluster, on_delete=models.CASCADE, related_name="agent_runs")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RUNNING)
    reproduced = models.BooleanField(default=False)
    category = models.CharField(max_length=30, blank=True)
    confidence = models.FloatField(default=0.0)
    explanation = models.TextField(blank=True)
    evidence = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-started_at"]


class AgentStep(models.Model):
    """One tool call in a diagnostic agent run — the audit log plan.md requires."""

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name="steps")
    index = models.IntegerField()
    tool = models.CharField(max_length=100)
    tool_input = models.JSONField(default=dict)
    tool_output = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["index"]


class FlakinessScore(models.Model):
    case = models.OneToOneField(TestCase, on_delete=models.CASCADE, related_name="score")
    # point estimate of flip probability + Wilson interval
    probability = models.FloatField(default=0.0)
    ci_low = models.FloatField(default=0.0)
    ci_high = models.FloatField(default=0.0)
    flip_commits = models.IntegerField(default=0)
    observed_commits = models.IntegerField(default=0)
    fail_count = models.IntegerField(default=0)
    run_count = models.IntegerField(default=0)
    avg_duration = models.FloatField(default=0.0)
    impact = models.FloatField(default=0.0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-impact"]


class QuarantineEntry(models.Model):
    case = models.ForeignKey(TestCase, on_delete=models.CASCADE, related_name="quarantines")
    reason = models.TextField(blank=True)
    created_by = models.CharField(max_length=200, blank=True)
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
