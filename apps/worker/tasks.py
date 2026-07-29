from core.services import analyze_project, diagnose_cluster, ingest_report

from worker.celery_app import app


@app.task(name="worker.process_report")
def process_report(
    project_id: int,
    commit_sha: str,
    branch: str,
    ci_run_id: str,
    xml_text: str,
    report_format: str = "junit",
):
    run = ingest_report(
        project_id=project_id,
        commit_sha=commit_sha,
        branch=branch,
        ci_run_id=ci_run_id,
        xml_text=xml_text,
        report_format=report_format,
    )
    analyze_project(project_id)
    return {"run_id": run.id}


@app.task(name="worker.diagnose")
def diagnose(cluster_id: int):
    """Runs the sandboxed diagnostic agent. Routed to the "diagnose" queue — only the
    opt-in `agent` service (docker.sock mounted) consumes it, never the ingest worker."""
    run = diagnose_cluster(cluster_id)
    return {"agent_run_id": run.id, "status": run.status}
