# FlakyRadar

Open-source, self-hosted flaky test detection for pytest / GitHub Actions.
Detects pass/fail flips on the same commit, scores flakiness with a Wilson score
interval, ranks tests by impact, and diagnoses root cause with AI (Phase 1+).

## Architecture

- `apps/ingest` — FastAPI, receives JUnit XML via webhook, enqueues a Celery job
- `apps/worker` — Celery, parses reports + computes flakiness scores
- `apps/dashboard` — Django + Admin, ranking, test detail, quarantine, diagnosis
- `packages/core` — models, scoring, JUnit parser, embeddings, clustering, LLM
  classification, shared by all three apps

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

## AI layer (root-cause diagnosis)

Set `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` in `.env` to enable it. After each
ingest, failing tests are embedded (Voyage AI), clustered by similarity
(HDBSCAN), and each cluster gets an LLM root-cause classification (Claude,
structured outputs) shown on the test detail page. Without the keys, ingestion
and scoring still work — the AI step is skipped.

## Status

Phase 0 + Phase 1 done: ingest, Wilson-score flakiness scoring, dashboard,
embedding + clustering + LLM root-cause diagnosis. Eval harness (Phase 2) is
next.
