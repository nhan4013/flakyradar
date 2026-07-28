# FlakyRadar

Open-source, self-hosted flaky test detection for pytest / GitHub Actions.
Detects pass/fail flips on the same commit, scores flakiness with a Wilson score
interval, ranks tests by impact, and diagnoses root cause with AI (Phase 1+).

## Architecture

- `apps/ingest` — FastAPI, receives JUnit XML via webhook, enqueues a Celery job
- `apps/worker` — Celery, parses reports + computes flakiness scores
- `apps/dashboard` — Django + Admin, ranking, test detail, quarantine
- `packages/core` — models, scoring, JUnit parser, shared by all three apps

## Run locally (Phase 0)

```bash
cp .env.example .env
docker compose up --build
```

- Dashboard: http://localhost:8000
- Ingest API: http://localhost:8001/healthz

Create a project + API key through Django Admin (`/admin/`, requires
`manage.py createsuperuser` first), then wire up the example GitHub Action in
[examples/github-action](examples/github-action).

## Dev without Docker

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DJANGO_TEST_SQLITE=1 .venv/bin/pytest -q
```

## Status

Phase 0 + Phase 1 (ingest, scoring, dashboard) scaffolded. AI layer (embeddings,
clustering, LLM classification) and eval harness are next.
