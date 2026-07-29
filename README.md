<p align="center">
  <em>Open-source, self-hosted flaky test detection, scoring, and AI diagnosis for CI</em>
</p>

<p align="center">
  <a href="https://github.com/nhan4013/flakyradar/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/nhan4013/flakyradar/actions/workflows/ci.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-blue.svg"></a>
  <img alt="Python 3.12" src="https://img.shields.io/badge/python-3.12-blue.svg">
</p>

---

Flaky tests — the ones that pass or fail on the same commit with no code
change — quietly eat CI budgets and developer trust everywhere. Google has
measured that 84% of test transitions from pass to fail in its CI are flaky,
not real bugs. FlakyRadar answers three questions for a pytest, Jest, JUnit,
or Go test suite: **which tests are flaky, how bad is it, and why** — and it's
something you run yourself, not a SaaS you have to trust with your CI data.

## Features

- **Flip detection & scoring** — flags tests that pass and fail on the same
  commit, scores flip probability with a Wilson score interval so tests with
  few observations don't outrank well-observed ones, and ranks by impact
  (flip rate × duration × failures).
- **Multi-framework ingestion** — pytest, JUnit (Java/Maven Surefire), Jest,
  and Go test, via one ingest API.
- **AI root-cause diagnosis** — embeds failing stack traces, clusters
  duplicate failures (HDBSCAN), and asks Claude to classify the root cause
  (race condition, test-order dependency, timing, network, resource leak).
- **RAG fix suggestions** — retrieves similar past fixes (hybrid BM25 +
  vector search) and asks Claude for a suggestion grounded in what actually
  fixed them before.
- **Sandboxed diagnostic agent** — a ReAct agent that reruns, reorders, and
  isolates the failing test inside a network-disabled Docker sandbox, with a
  hard step/token budget and a full tool-call audit log — not a black box.
- **Multi-tenant dashboard** — per-user login scoped to project membership.

## Quick start

```bash
git clone https://github.com/nhan4013/flakyradar.git
cd flakyradar
cp .env.example .env
docker compose up --build
docker compose exec dashboard python manage.py createsuperuser
```

- Dashboard: http://localhost:8000 (log in at `/accounts/login/`)
- Ingest API: http://localhost:8001/healthz

Create a project + API key through Django Admin (`/admin/`), add the
dashboard users who should see it under the project's "members", then wire
the example GitHub Action in [examples/github-action](examples/github-action)
into your CI.

## Supported report formats

Pass `report_format` on the upload (defaults to `junit`):

| `report_format` | Covers | How to produce it |
|---|---|---|
| `junit` (default) | pytest, JUnit (Java/Maven Surefire) | `pytest --junitxml=report.xml`, or Maven/Gradle's built-in surefire XML |
| `jest-json` | Jest | `jest --json --outputFile=report.json` |
| `go-test-json` | Go test | `go test -json ./... > report.json` |

(Jest via `jest-junit` also works — same XML schema as `junit`, no separate
format needed for that path.)

## Architecture

```
apps/ingest      FastAPI — receives a test report via webhook, enqueues a Celery job
apps/worker      Celery — parses reports, scores flakiness, runs the AI pipeline
apps/dashboard   Django — login, ranking, test detail, quarantine, diagnosis
packages/core    models, scoring, report parsers, embeddings, clustering,
                 LLM classification, retrieval, sandbox — shared by all three apps
```

## AI-powered diagnosis

Set `ANTHROPIC_API_KEY` and `VOYAGE_API_KEY` in `.env` to enable it. After
each ingest, failing tests are embedded (Voyage AI), clustered by similarity
(HDBSCAN), and each cluster gets an LLM root-cause classification (Claude,
structured outputs) shown on the test detail page. Without the keys,
ingestion and scoring still work — the AI step is skipped.

Mark a cluster resolved via Django Admin by adding a `FixRecord` (commit SHA +
description). Future clusters are matched against resolved ones with hybrid
retrieval — BM25 text match + embedding cosine similarity, fused by
reciprocal rank fusion — and Claude turns the top matches into a grounded
suggestion ("similar to X, fixed via commit Y").

## Diagnostic agent

Click "Diagnose (sandboxed agent)" on a test's detail page to have a ReAct
agent (Claude, manual tool-use loop) investigate a flaky cluster against a
real, sandboxed checkout of the test's repo at the commit it failed on:

- **Tools**: `rerun_test(n)`, `run_with_random_order()`, `run_in_isolation()`,
  `read_test_source(path)`, `check_shared_fixtures()`
- **Sandbox**: `docker build` installs the repo's deps (network on for
  that step only); every actual test run is `docker run --network none`
  with CPU/RAM/pids/time limits
- **Budget**: a hard step cap (`AGENT_MAX_STEPS`, default 8) and token cap
  (`AGENT_MAX_TOKENS`, default 50000) — the agent reports "budget exhausted"
  instead of running forever
- **Audit log**: every tool call, input, and output is recorded and
  viewable on the agent run detail page

Requires `Project.repo_url` set (Django Admin) and `ANTHROPIC_API_KEY`.

The agent needs its own Celery worker with the **host docker socket
mounted** so it can build sandbox images and run containers — a materially
stronger trust boundary than the ingest worker. It's therefore an opt-in,
separate service, never started by plain `docker compose up`:

```bash
docker compose --profile agent up
```

Don't enable this on a host you don't control.

## Eval harness

```bash
PYTHONPATH=packages python scripts/run_eval.py
```

- **Retrieval precision@1: 1.00** (n=3, synthetic cases — deterministic,
  runs offline, no API key needed)
- **Classifier accuracy/F1** — needs `ANTHROPIC_API_KEY`; scores against
  `packages/core/eval_data.py`, a small hand-curated seed set standing in
  for a public dataset (e.g. FlakeFlagger) — not mined data

Both run in CI; the classifier step no-ops without the `ANTHROPIC_API_KEY`
secret configured.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DJANGO_TEST_SQLITE=1 .venv/bin/pytest -q
ruff check .
```

## Roadmap

- [x] Flip detection, Wilson-score scoring, dashboard
- [x] Multi-framework ingestion (pytest, JUnit, Jest, Go test)
- [x] AI root-cause classification + RAG fix suggestions
- [x] Eval harness (classifier F1, retrieval precision@k)
- [x] Sandboxed ReAct diagnostic agent
- [x] Multi-tenant dashboard (per-user login, project membership)
- [ ] Distill a small fine-tuned classifier and compare accuracy vs. cost
- [ ] Public hosted demo

## Contributing

Issues and pull requests are welcome. This is an early-stage solo project —
open an issue before a large PR so the direction can be agreed on first.

## License

[MIT](LICENSE)
