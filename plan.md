# FlakyRadar — Kế hoạch xây dựng dự án

> Nền tảng open-source, self-hosted: phát hiện, chấm điểm và chẩn đoán flaky test cho CI (pytest / GitHub Actions), tích hợp AI ở tầng phân tích.

---

## 1. Tổng quan

### Vấn đề
Flaky test (test lúc pass lúc fail trên cùng một commit) là "thuế" mà hầu hết team phải trả: Google đo được 84% các lần chuyển pass→fail trong CI là flaky chứ không phải bug thật; Microsoft đo trung bình 30 phút cho mỗi lần điều tra; Atlassian ước tính mất 150.000 giờ dev/năm. Các tool thương mại (Harness, BuildPulse, Datadog CI Visibility) đều là SaaS trả phí — bản open-source self-hosted cho hệ sinh thái pytest/GitHub Actions gần như trống.

### Sản phẩm trả lời 3 câu hỏi
1. **Test nào đang flaky?** — phát hiện bằng thống kê trên lịch sử test run
2. **Flaky đến mức nào?** — chấm điểm xác suất + xếp hạng tác động
3. **Vì sao flaky?** — AI phân loại root cause, gợi ý hướng fix, agent tự tái hiện

### Mục tiêu cá nhân
- Portfolio thể hiện đồng thời: backend engineering (FastAPI/Django/Celery/AWS) + AI engineering (embeddings, RAG, agents, evals)
- Mỗi phase ra 1 bài blog trên blog.lucaspham.org
- Dogfood trên CI của chính DevMemory và FlakyRadar
- Đạt mốc có người dùng thật (Show HN, r/django, r/python)

---

## 2. Tech stack

| Tầng | Công nghệ | Vai trò |
|---|---|---|
| Ngôn ngữ | Python 3.12 | — |
| Ingest API | FastAPI | Nhận webhook GitHub Actions, upload JUnit XML |
| Dashboard | Django + Django Admin | Xếp hạng flaky, lịch sử, quarantine, quản lý project/API key |
| Xử lý nền | Celery | Parse report, tính điểm, clustering, gọi LLM, chạy agent |
| Database | PostgreSQL + pgvector | Lịch sử test run + vector store (MVP không cần Qdrant riêng) |
| Cache/Broker | Redis | Celery broker (local), cache |
| AWS | S3, SQS, ECS Fargate, CloudWatch, Terraform | Lưu log thô, queue production, deploy, metrics, IaC |
| LLM | Anthropic API (Claude) | Root-cause classification (structured outputs), gợi ý fix, LLM-as-judge |
| Embeddings | Voyage AI / OpenAI embeddings | Embed stack trace |
| Thuật toán | Wilson score / Beta-Binomial, HDBSCAN, BM25 + vector (hybrid) | Chấm điểm flaky, cluster lỗi, retrieval |
| Agent | ReAct tự viết bằng Anthropic SDK, Docker sandbox | Tự tái hiện lỗi có kiểm soát |
| Eval | pytest + dataset FlakeFlagger, LLM-as-judge trong CI | Đo accuracy/F1, precision@k |
| DevOps | Docker, docker-compose, GitHub Actions | Dev local, CI, GitHub Action mẫu cho người dùng |

---

## 3. Kiến trúc tổng thể

```
GitHub Actions (repo người dùng)
        │  webhook + JUnit XML
        ▼
   FastAPI (ingest) ──► S3 (log thô)
        │  push job
        ▼
   Redis/SQS ──► Celery workers
                    │
       ┌────────────┼──────────────────┐
       ▼            ▼                  ▼
  Parse report   Scoring engine    AI pipeline
  (JUnit XML)    (Wilson score,    (embed → HDBSCAN
                  impact rank)      → LLM classify
       │            │               → RAG suggest)
       └────────────┴───────┬───────┘
                            ▼
                  PostgreSQL + pgvector
                            │
                            ▼
                  Django dashboard + Admin
                  (ranking, quarantine, replay,
                   báo cáo chẩn đoán, alert Slack/Telegram)
```

---

## 4. Data model chính (phác thảo)

- `Project` — repo, API key, cấu hình
- `TestRun` — commit SHA, branch, CI run ID, thời điểm, môi trường
- `TestCase` — định danh test (file::class::name)
- `TestResult` — kết quả 1 test trong 1 run (pass/fail/skip, duration, stack trace ref → S3)
- `FlakinessScore` — điểm theo thời gian cho mỗi TestCase (xác suất, khoảng tin cậy, impact)
- `FailureCluster` — nhóm lỗi (centroid embedding, đại diện, root-cause label)
- `Diagnosis` — kết quả LLM/agent: category, confidence, giải thích, gợi ý fix, evidence
- `QuarantineEntry` — test bị cách ly, lý do, người quyết định

---

## 5. Roadmap

### Phase 0 — Setup (3–4 ngày)
- [ ] Repo monorepo: `apps/ingest` (FastAPI), `apps/dashboard` (Django), `apps/worker` (Celery), `packages/core`
- [ ] docker-compose: Postgres + pgvector, Redis, các service
- [ ] CI của chính project (lint, test, type-check)
- [ ] Terraform skeleton cho AWS (chưa deploy)

**Định nghĩa xong**: `docker compose up` chạy được cả hệ, healthcheck xanh.

### Phase 1 — MVP: Detect & Score (tuần 1–4)

**Tuần 1 — Ingestion**
- [ ] FastAPI endpoint nhận JUnit XML + metadata (commit, branch, run ID)
- [ ] Xác thực API key, đẩy raw file lên S3, enqueue Celery job
- [ ] Celery task parse JUnit XML → ghi TestRun/TestResult
- [ ] GitHub Action mẫu (`flakyradar-upload`) để người dùng cắm vào repo trong 5 phút

**Tuần 2 — Scoring engine (thuật toán)**
- [ ] Phát hiện flip trên cùng commit (pass↔fail, không đổi code)
- [ ] Wilson score interval / Beta-Binomial → xác suất flaky kèm độ tin cậy
- [ ] Impact score = tần suất flaky × duration × số PR bị chặn
- [ ] Unit test cho toàn bộ công thức (đây là phần khoe được trong phỏng vấn)

**Tuần 3 — Dashboard**
- [ ] Django: bảng xếp hạng test flaky (score, trend, lần fail gần nhất)
- [ ] Trang chi tiết test: lịch sử run, stack trace, biểu đồ pass/fail theo thời gian
- [ ] Quarantine list + Django Admin cho quản trị
- [ ] Alert cơ bản: test mới bị gắn cờ flaky → Slack/Telegram webhook

**Tuần 4 — AI lớp 1+2**
- [ ] Embed stack trace → pgvector; HDBSCAN gom cluster lỗi trùng
- [ ] LLM classify root cause (structured outputs, few-shot): race condition / test-order / timing / network / resource leak
- [ ] Hiển thị cluster + diagnosis trên dashboard
- [ ] Dogfood: cắm FlakyRadar vào CI của DevMemory và của chính nó

**Định nghĩa xong Phase 1**: một repo thật đẩy report tự động, dashboard xếp hạng đúng, mỗi test flaky có nhãn root cause.
**Blog #1**: "Tôi build máy phát hiện flaky test bằng Wilson score và HDBSCAN"

### Phase 2 — RAG + Eval harness (tuần 5–7)

**Tuần 5 — RAG trên lịch sử team**
- [ ] Index các cluster đã đóng + commit fix (GitHub API)
- [ ] Hybrid retrieval: BM25/Postgres FTS + vector, rerank
- [ ] LLM sinh gợi ý: "lỗi tương tự từng được fix bằng cách X — xem commit Y"

**Tuần 6–7 — Eval harness**
- [ ] Chuẩn hóa dataset flaky test công khai (FlakeFlagger và tương đương) làm ground truth
- [ ] Đo accuracy/F1 của classifier; precision@k của retrieval
- [ ] LLM-as-judge chấm chất lượng gợi ý fix
- [ ] Chạy eval trong CI, xuất báo cáo — model mới ra thì swap vào đo lại

**Định nghĩa xong Phase 2**: có số liệu công khai trong README ("classifier đạt X% F1 trên N mẫu").
**Blog #2**: "Xây eval harness cho LLM pipeline: bài học từ FlakyRadar"

### Phase 3 — Diagnostic Agent (tuần 8–10)

- [ ] ReAct agent với tool: `rerun_test(n)`, `run_with_random_order()`, `run_in_isolation()`, `read_test_source()`, `check_shared_fixtures()`
- [ ] Docker sandbox: network tắt mặc định, giới hạn CPU/RAM/thời gian, allowlist rõ ràng
- [ ] Budget: giới hạn số step + chi phí token mỗi lần chẩn đoán
- [ ] Log đầy đủ mọi tool call để audit; báo cáo chẩn đoán kèm bằng chứng
- [ ] Đo tỷ lệ agent tái hiện thành công trên dataset eval

**Định nghĩa xong Phase 3**: bấm "Diagnose" trên dashboard → agent chạy trong sandbox → trả báo cáo có bằng chứng.
**Blog #3**: "Build agent tự tái hiện flaky test — và sandbox nó tử tế (bài học từ vụ GPT-5.6 Sol)"

### Phase 4 — Tùy chọn / dài hạn
- [ ] Distill: fine-tune model nhỏ (LoRA trên vast.ai) từ nhãn của Phase 1–2, so accuracy vs chi phí
- [ ] Hỗ trợ thêm framework: Jest, JUnit (Java), Go test
- [ ] Multi-tenant hoàn chỉnh, deploy bản demo public
- [ ] Show HN + post r/django, r/python, r/QualityAssurance

---

## 6. Deliverables cho CV & job search

**Bullet mẫu (điền số thật sau khi đo):**
- Built FlakyRadar, an open-source flaky-test detection platform (FastAPI, Django, Celery, PostgreSQL/pgvector, AWS) processing N test results/day across M repositories
- Implemented Bayesian flakiness scoring (Wilson score / Beta-Binomial) and HDBSCAN failure clustering, reducing duplicate failure triage by X%
- Designed an LLM root-cause classification pipeline with structured outputs achieving X% F1 on a public labeled dataset, validated by a CI-integrated eval harness with LLM-as-judge
- Developed a sandboxed ReAct diagnostic agent (Docker, resource limits, full audit logging) that automatically reproduces flaky tests with X% success rate

**Chuỗi blog (mỗi phase một bài, đăng blog.lucaspham.org + dev.to):**
1. Wilson score + HDBSCAN cho flaky detection
2. Eval harness cho LLM pipeline
3. Sandboxed diagnostic agent

---

## 7. Rủi ro & cách né

| Rủi ro | Cách né |
|---|---|
| Scope creep, làm mãi không ship | Ship Phase 1 trước khi viết dòng code nào của Phase 2; mỗi phase có định nghĩa xong rõ ràng |
| Chi phí LLM API | Prompt caching, chỉ classify khi có cluster mới, batch; Phase 4 distill model nhỏ |
| Thiếu dữ liệu thật để demo | Dogfood trên DevMemory + tự tạo repo demo có flaky test cố ý (sleep, random, shared state) |
| Agent sandbox rủi ro | Network off mặc định, giới hạn tài nguyên, budget step/token, audit log — thiết kế trước khi code |
| Trùng với tool có sẵn | Định vị rõ: open-source, self-hosted, pytest-first — khác phân khúc với SaaS trả phí |

---

## 8. Chỉ số thành công

- [ ] Phase 1 ship trong 4 tuần, dogfood chạy thật
- [ ] Eval công khai: F1 classifier, precision@k retrieval, tỷ lệ agent tái hiện
- [ ] ≥ 3 bài blog xuất bản
- [ ] ≥ 1 repo ngoài (không phải của mình) dùng thử
- [ ] 100+ GitHub stars sau Show HN (mục tiêu tham vọng nhưng đo được)