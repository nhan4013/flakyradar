from core.services import ingest_report

from worker.celery_app import app


@app.task(name="worker.process_report")
def process_report(project_id: int, commit_sha: str, branch: str, ci_run_id: str, xml_text: str):
    run = ingest_report(
        project_id=project_id,
        commit_sha=commit_sha,
        branch=branch,
        ci_run_id=ci_run_id,
        xml_text=xml_text,
    )
    return {"run_id": run.id}
