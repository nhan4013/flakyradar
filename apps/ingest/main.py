"""FastAPI ingest endpoint. Validates project API key, stores raw XML to S3 (or local disk
in dev), and enqueues a Celery task to parse + score. Kept thin — parsing/scoring live in
packages/core so both this API and tests exercise the same code path."""

import os
import uuid
from datetime import UTC, datetime

import boto3
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, Header, HTTPException, UploadFile

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django

django.setup()

from core import report_formats
from core.models import Project
from worker.tasks import process_report

app = FastAPI(title="FlakyRadar Ingest")

S3_BUCKET = os.environ.get("S3_BUCKET", "")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL") or None


def get_s3_client():
    return boto3.client("s3", endpoint_url=S3_ENDPOINT_URL)


async def authenticate(x_api_key: str = Header(...)) -> Project:
    project = await Project.objects.filter(api_key=x_api_key).afirst()
    if project is None:
        raise HTTPException(status_code=401, detail="invalid API key")
    return project


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/v1/reports")
async def upload_report(
    commit_sha: str,
    branch: str = "main",
    ci_run_id: str = "",
    report_format: str = "junit",
    file: UploadFile = None,
    project: Project = Depends(authenticate),
):
    if file is None:
        raise HTTPException(status_code=400, detail="missing file")
    if report_format not in report_formats.PARSERS:
        raise HTTPException(status_code=400, detail=f"unsupported report_format: {report_format!r}")
    raw = await file.read()
    xml_text = raw.decode("utf-8", errors="replace")

    key = f"{project.slug}/{datetime.now(UTC):%Y/%m/%d}/{uuid.uuid4()}.xml"
    if S3_BUCKET:
        try:
            get_s3_client().put_object(Bucket=S3_BUCKET, Key=key, Body=raw)
        except ClientError as exc:
            raise HTTPException(status_code=502, detail=f"S3 upload failed: {exc}") from exc

    task = process_report.delay(project.id, commit_sha, branch, ci_run_id, xml_text, report_format)
    return {"status": "queued", "task_id": task.id, "s3_key": key if S3_BUCKET else None}
