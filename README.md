# FlakyRadar

Open-source, self-hosted flaky test detection cho pytest / GitHub Actions.
Phát hiện flip pass/fail trên cùng commit, chấm điểm bằng Wilson score interval,
xếp hạng theo impact, chẩn đoán root cause bằng AI (Phase 1+).

Xem [plan.md](plan.md) cho roadmap đầy đủ.

## Kiến trúc

- `apps/ingest` — FastAPI, nhận JUnit XML qua webhook, enqueue Celery job
- `apps/worker` — Celery, parse report + tính flakiness score
- `apps/dashboard` — Django + Admin, bảng xếp hạng, chi tiết test, quarantine
- `packages/core` — models, scoring, JUnit parser, dùng chung bởi cả 3 app

## Chạy local (Phase 0)

```bash
cp .env.example .env
docker compose up --build
```

- Dashboard: http://localhost:8000
- Ingest API: http://localhost:8001/healthz

Tạo project + API key qua Django Admin (`/admin/`, cần `manage.py createsuperuser` trước),
rồi cắm GitHub Action mẫu trong [examples/github-action](examples/github-action).

## Dev không cần Docker

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
DJANGO_TEST_SQLITE=1 .venv/bin/pytest -q
```

## Trạng thái

Phase 0 + Phase 1 (ingest, scoring, dashboard) đã dựng khung. AI layer (embedding,
clustering, LLM classify) và eval harness — xem plan.md Phase 1 tuần 4 trở đi.
