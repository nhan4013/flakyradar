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

    class Meta:
        indexes = [models.Index(fields=["case", "run"])]


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
