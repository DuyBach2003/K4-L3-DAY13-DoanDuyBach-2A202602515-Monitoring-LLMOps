# Báo cáo cá nhân — K4-L3A Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Đoàn Duy Bách
- **MSSV:** 2A202602515
- **Lớp:** K4-L3A
- **Repository URL:** https://github.com/DuyBach2003/K4-L3-DAY13-DoanDuyBach-2A202602515-Monitoring-LLMOps
- **Commit SHA cuối:** `8dafdf32bef43af663e42c59dfe46be2171bf1f7`
- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3a-02515`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | [01-pytest.txt](evidence/01-pytest.txt) |
| Log validator | [02-log-validator.txt](evidence/02-log-validator.txt) |
| Dashboard validator | [03-dashboard-validator.txt](evidence/03-dashboard-validator.txt) |
| Structured log | [04-structured-log.png](evidence/04-structured-log.png), [04-structured-log.txt](evidence/04-structured-log.txt) |
| PII redaction | [05-pii-redaction.png](evidence/05-pii-redaction.png), [05-pii-redaction.txt](evidence/05-pii-redaction.txt) |
| Trace list | [06-trace-list.png](evidence/06-trace-list.png) |
| Trace waterfall | [07-trace-waterfall.png](evidence/07-trace-waterfall.png), [07-trace-waterfall.txt](evidence/07-trace-waterfall.txt) |
| Trace metadata | [08-trace-metadata.png](evidence/08-trace-metadata.png) |
| Prompt versions | [09-prompt-versions.png](evidence/09-prompt-versions.png) |
| Prompt rollback | [10-prompt-rollback.png](evidence/10-prompt-rollback.png) |
| Dashboard runtime | [11-dashboard-overview.png](evidence/11-dashboard-overview.png) |
| Incident metric | [12-incident-metric.png](evidence/12-incident-metric.png), [12-incident-metric.txt](evidence/12-incident-metric.txt) |
| Incident log | [13-incident-log.png](evidence/13-incident-log.png), [13-incident-log.txt](evidence/13-incident-log.txt) |
| Incident trace | [14-incident-trace.png](evidence/14-incident-trace.png), [14-incident-trace.txt](evidence/14-incident-trace.txt) |
| Metrics snapshot | [metrics-snapshot.json](evidence/metrics-snapshot.json) |

Ảnh Langfuse `08` và `14` đã che giá trị `scope.attributes.public_key`; không chỉnh sửa nội dung khác.

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | chưa đo (TODO chưa làm) | 100/100 | 0 PII leak, 10 correlation ID |
| `validate_dashboard.py` | 6/6 | 6/6 | contract đã có sẵn |
| `pytest` | 22 pass (starter) | 24 pass | thêm test CCCD/thẻ/passport |
| Số traces hợp lệ | 0 | 12 root traces (37 observations, env `dev`) | `evidence/06-trace-list.png`; đạt yêu cầu ≥10 traces |
| Số PII leak | chưa đo | 0 | validator quét toàn bộ `data/logs.jsonl`; email/SĐT/CCCD/thẻ đều thành `[REDACTED_*]` ([05 png](evidence/05-pii-redaction.png), [05 txt](evidence/05-pii-redaction.txt)) |
| Latency P95 / TTFT P95 | chưa đo | 160ms / 55ms | P50 159ms, P99 160ms ([metrics-snapshot.json](evidence/metrics-snapshot.json)); rất xa ngưỡng SLO 3000ms |
| Retrieval success rate | chưa đo | 100% (41/41) | tính từ `tool_success` của các event `response_sent` trong `data/logs.jsonl`; guardrail ≥ 90% |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` lấy `x-request-id` hoặc sinh `req-<8hex>`, `clear_contextvars()` rồi `bind_contextvars`, trả lại qua header `x-request-id` và `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `user_id_hash`, `session_id`, `feature`, `model`, `env` bind trong `/chat` ([app/main.py](../app/main.py)).
- **Cách bảo đảm PII được scrub trước khi ghi:** `scrub_event` đăng ký trước `JsonlFileProcessor`/JSONRenderer; thêm pattern passport; scrub cả field chuỗi top-level.
- **Cách kiểm chứng kết quả:**
  - Gửi request có header `x-request-id` và không có header: response luôn trả `x-request-id` (giữ nguyên ID gửi lên hoặc sinh `req-<8hex>`) cùng `x-response-time-ms`. Mỗi request có một ID riêng (11 correlation ID khác nhau trong [02](evidence/02-log-validator.txt)), nên context không bị rò giữa các request.
  - `validate_logs.py`: 100/100, 0 bản ghi thiếu field hoặc thiếu enrichment, 0 PII leak ([02](evidence/02-log-validator.txt)).
  - Gửi message có đủ email, SĐT, CCCD và số thẻ (`req-5bdc4330`): log line `request_received` chỉ còn `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`. `message_preview` bị cắt ở 80 ký tự nên phần số thẻ chỉ còn `card...`; vì vậy evidence có thêm log `req-e16a57e3` chứa `[REDACTED_CREDIT_CARD]`, output `scrub_text` trên đúng input đó (số thẻ thành `[REDACTED_CREDIT_CARD]`), và `grep` số thẻ/email/SĐT/CCCD thô trong `data/logs.jsonl` ra 0 dòng ([05 png](evidence/05-pii-redaction.png), [05 txt](evidence/05-pii-redaction.txt)).
  - `tests/test_pii.py` có thêm test cho CCCD, thẻ và passport; `pytest` 24/24 pass ([01](evidence/01-pytest.txt)).

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** tự chạy `scripts/load_test.py` và các request `/chat` với key của project `day13-k4-l3a-02515`; trace list lọc Past 1 day, `isRootObservation:true` cho ra Total 12 trace `day13-agent-request`, mỗi trace một `correlation_id` riêng ([06](evidence/06-trace-list.png)).
- **Cấu trúc root/retrieval/generation observations:** root `lab-agent-run` (agent) có hai child ngang hàng là `retrieval` (retriever) và `llm-generate` (generation, có model, usage và cost), tạo trong [app/agent.py](../app/agent.py). Kiểm chứng trên trace `c5bc5416ad4e037a4db759b9a5b5eaf6` (prompt `day13-chat` v2, `prompt_source=langfuse`), chế độ Tree, chọn `llm-generate`: root 1101ms; `retrieval` và `llm-generate` đều có `parentObservationId=f86ba72addcc8826` (root); `llm-generate` 158ms, model `claude-sonnet-4-5`, `Prompt: day13-chat - v2`, usage 35 in / 99 out / 134 total, cost $0.00159 ([07 png](evidence/07-trace-waterfall.png), [07 txt](evidence/07-trace-waterfall.txt)).
- **Cách nối trace với log:** trace metadata có `correlation_id` (ví dụ `req-ee306d64` ở trace `c5bc5416ad4e037a4db759b9a5b5eaf6`, [08](evidence/08-trace-metadata.png)); `grep req-ee306d64 data/logs.jsonl` ra đúng 2 log line `request_received` và `response_sent` của request đó (latency 1099ms, 134 tokens, $0.00159 — khớp với trace).
- **Prompt name:** `day13-chat` (text prompt, giữ ba biến `feature`, `docs`, `message`).
- **Version/label baseline:** version #1, labels `baseline` + `production` ([09](evidence/09-prompt-versions.png)).
- **Version/label candidate:** version #2, label `candidate`, thêm dòng `Answer concisely in 3 bullet points.`
- **Trace ID của mỗi version:**
  - Version #1: `9c2df364ff0c3727c91e0a3fad41a2a7` (`correlation_id=req-318971e0`), chạy với `LANGFUSE_PROMPT_LABEL=baseline`; metadata `prompt_source=langfuse`, `prompt_version=1`, `prompt_label=baseline`; 157 tokens, $0.002043.
  - Version #2: `c5bc5416ad4e037a4db759b9a5b5eaf6` (`correlation_id=req-ee306d64`), chạy với `LANGFUSE_PROMPT_LABEL=production` sau khi promote; metadata `prompt_source=langfuse`, `prompt_version=2`, `prompt_label=production`; 134 tokens, $0.00159 ([08](evidence/08-trace-metadata.png)).
  - Cùng input `Explain observability`, `tokens_in` tăng từ 26 lên 35 vì version #2 thêm một dòng hướng dẫn. `tokens_out` do mock LLM sinh ngẫu nhiên nên chưa dùng để so sánh chất lượng giữa hai version.
- **Cách promote và rollback `production`:** trong trang prompt, chuyển label `production` từ version #1 sang #2 ([10](evidence/10-prompt-rollback.png), ảnh trên: trước, ảnh dưới: sau khi promote). Rollback là thao tác ngược lại: gán `production` về version #1; app lấy prompt theo label nên không cần deploy lại.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** dashboard `K4-L3A Day 13 Monitoring & LLMOps` dựng từ `data/logs.jsonl` bằng [scripts/render_dashboard.py](../scripts/render_dashboard.py), đọc trực tiếp panel, đơn vị và threshold từ [config/dashboard.yaml](../config/dashboard.yaml); time range 60 phút, bucket 1 phút, refresh 30s ([11](evidence/11-dashboard-overview.png)). Sáu panel đều có đường threshold nét đứt màu đỏ. Số liệu trong ảnh (128 request, 15:13–16:13): Latency P50 159ms / P95 2666ms / P99 2667ms / TTFT P95 55ms (ngưỡng P95 ≤ 3000ms); Traffic trung bình 10.7 req/phút (≥ 1); Error rate 0%, retrieval success 100% (≤ 2%); Cost tổng $0.2639 (≤ $2.5); Tokens in/out 5,524 / 16,488 (≤ 50,000); Quality mean 0.88 (≥ 0.75). Đỉnh P95/P99 khoảng 2.66s trong khoảng 16:05–16:07 là incident `rag_slow` (log `incident_enabled` 09:05:13Z → `incident_disabled` 09:07:19Z): 26 request liên tiếp đều khoảng 2660ms. P95 vẫn dưới ngưỡng dashboard 3000ms, nhưng vượt `latency_threshold_ms: 2000` của challenge. `quality_score` cũng được gửi lên Langfuse dưới dạng trace score ([app/agent.py](../app/agent.py)), nên panel Quality Score trên dashboard Langfuse có dữ liệu (129 score, trung bình 0.877).
- **SLO và lý do chọn:** `fast_successful_requests` ([config/slo.yaml](../config/slo.yaml)): 99.5% request `request_received` phải có `response_sent` với `latency_ms ≤ 3000` trong cửa sổ 28 ngày. SLO này gộp cả lỗi và độ chậm, đúng với cảm nhận của người dùng. Tôi giữ ngưỡng 3000ms vì baseline chỉ có P95 = P99 = 160ms: còn đủ headroom cho dao động bình thường, nhưng một incident như `rag_slow` (retrieval chậm vài giây) sẽ vượt ngưỡng và bị đếm là bad event.
- **Cách tính error budget:** error budget = 100% − 99.5% = 0.5%, tức 5 bad event trên mỗi 1000 request. Theo thời gian: 0.5% × 28 ngày × 24h ≈ 3.4 giờ nếu toàn bộ traffic hỏng liên tục. Baseline hiện tại có 41/41 request đạt (0 bad event), nên chưa tiêu budget. Khi đã tiêu hết budget thì ưu tiên sửa độ ổn định thay vì ra prompt/feature mới.
- **Ba alert và runbook tương ứng:** [config/alert_rules.yaml](../config/alert_rules.yaml), [docs/alerts.md](../docs/alerts.md), cả ba đều gửi Slack `#day13-alerts`:
  - `high_latency_p95` (P2, 5m, on-call-backend): P95 `latency_ms` > 3000ms, bảo vệ trực tiếp SLO latency.
  - `high_error_rate` (P1, 5m, on-call-backend): `request_failed / request_received` > 2%. Là P1 vì người dùng nhận HTTP 500.
  - `daily_cost_spike` (P3, 15m, on-call-llmops): tổng `cost_usd` > $2.5/ngày hoặc `tokens_out` > 3× baseline. Dùng duration dài hơn vì cost là tín hiệu tích lũy, không cần page ngay.
  - Mỗi runbook ghi ba bước kiểm tra theo thứ tự panel → log (lấy `correlation_id`) → trace, kèm mitigation tạm thời.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3a-monitoring-llmops-v1` (cohort K4, incident `rag_slow`, seed 1311, `affected_feature=monitoring`, `latency_threshold_ms=2000`). Chạy bằng `python scripts/inject_incident.py` rồi `python scripts/load_test.py --challenge --concurrency 5`. File challenge lưu tại `config/challenge.json` (đã `.gitignore`).
- **Khoảng thời gian điều tra:** 2026-09-29 09:05:13Z → 09:07:19Z (16:05–16:07 giờ VN), từ log `incident_enabled` đến `incident_disabled`. Năm query challenge nằm trong 09:05:13Z–09:05:27Z.
- **Triệu chứng từ metrics:** P95 latency tăng từ 160ms lên 2667ms, P99 lên 2668ms. Cả 5/5 query challenge vượt ngưỡng 2000ms. Trong khi đó TTFT P95 vẫn 55ms, error rate 0%, retrieval success 100%, tokens/cost không đổi ([12 png](evidence/12-incident-metric.png), [12 txt](evidence/12-incident-metric.txt)). Latency tăng mà TTFT không đổi nghĩa là thời gian bị thêm vào **trước** bước generation, không phải do LLM hay lỗi.
- **Log line và correlation ID liên quan:** `req-4c129a7d` (session `k4-l3a-challenge-s03`): `response_sent` lúc 09:05:16.246Z với `latency_ms=2659`, `ttft_ms=55`, `tool_name=retrieval`, `tool_success=true`. Bốn request còn lại (`req-e2ac6712`, `req-1cabb84f`, `req-039618d3`, `req-56d251a4`) có cùng mẫu, 2664–2668ms ([13 png](evidence/13-incident-log.png), [13 txt](evidence/13-incident-log.txt)).
- **Trace ID và span gây ảnh hưởng:** trace `57c97e9564d69ddbe9684efd874331d7` có metadata `correlation_id=req-4c129a7d`. Root `lab-agent-run` 2660ms; child `retrieval` (RETRIEVER) **2502ms (94%)**; `llm-generate` 156ms (6%, bằng baseline ~160ms). Cả 5 trace challenge đều như vậy, retrieval 2502–2506ms ([14 png](evidence/14-incident-trace.png), [14 txt](evidence/14-incident-trace.txt)).
- **Root cause:** bước retrieval (`app/mock_rag.py::retrieve`) bị chậm thêm cố định ~2.5s mỗi request khi cờ incident `rag_slow` bật (`time.sleep(2.5)` giả lập vector store/RAG backend chậm). Metric (P95 tăng, TTFT không đổi), log (`latency_ms` ≈ 2660, `tool_success=true`) và trace (span `retrieval` chiếm 94%) cùng chỉ về một nguyên nhân. Có một hệ quả phụ: `/chat` là `async def` nhưng gọi `agent.run` đồng bộ nên chặn event loop. Vì vậy 5 request song song bị xử lý nối tiếp, client đo được ~13.3s/request dù mỗi request trên server chỉ ~2.66s.
- **Fix action:** tắt nguồn gây chậm (`python scripts/inject_incident.py --disable`, lúc 09:07:19Z). Kiểm chứng: 11 request sau đó có P95 161ms, 0 request > 2000ms (request `req-0d61e443` cùng query challenge chỉ còn 160ms). Trong hệ thống thật, bước tương ứng là rollback/khôi phục backend retrieval. Ngoài ra nên chạy `agent.run` trong threadpool (khai báo `def chat` hoặc dùng `run_in_threadpool`) để một dependency chậm không chặn các request khác.
- **Preventive measure:**
  - Thêm timeout cho retrieval (ví dụ 500ms) kèm fallback, ghi `tool_success=false` khi timeout để sự cố hiện lên panel retrieval success thay vì chỉ làm tăng latency.
  - Thêm alert riêng cho latency của span retrieval (ví dụ P95 > 1000ms trong 5 phút). Alert `high_latency_p95` hiện tại dùng ngưỡng 3000ms nên **không bắt được** incident này (P95 2667ms vẫn được dashboard đánh dấu "đạt"), dù ngưỡng challenge là 2000ms.
  - Ghi `retrieval_ms` vào log `response_sent` để có metric theo từng bước mà không cần mở trace.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** tách việc tạo child observation vào helper `start_observation` ([app/tracing.py](../app/tracing.py)). Helper trả `nullcontext()` khi không có key Langfuse hoặc SDK. Nhờ vậy `pytest` và môi trường không có `.env` vẫn chạy đúng mà không phải rải `if tracing_enabled()` khắp `agent.py`. Ngoài ra, input/output đưa vào span chỉ là `summarize_text(...)` (bản rút gọn đã scrub) chứ không phải raw prompt, để trace không chứa PII.
- **Một lỗi/blocker đã gặp:** các trace đầu tiên (ví dụ `9b356ed0ba043bdb060bd57193b7f32c`) có `prompt_source=local-fallback`, `prompt_version=local-v1`, `prompt_fetch_error=LangfuseFallback` thay vì prompt `day13-chat` trên Langfuse. Sau khi xử lý, trace mới ghi `prompt_source=langfuse`, `prompt_version=2` ([08](evidence/08-trace-metadata.png)).
- **Cách tìm nguyên nhân và xử lý:** đọc metadata của trace và so với `resolve_prompt` ([app/prompt_management.py](../app/prompt_management.py)). Khi không lấy được prompt theo name/label, app fallback sang prompt local. Nguyên nhân: các trace này được tạo trước khi tôi tạo prompt `day13-chat` trên Langfuse. Cách xử lý: tạo prompt v1 (`baseline`, `production`) và v2 (`candidate`), rồi chạy lại workload theo từng label để trace ghi đúng name/version/label. Ngoài ra, API trước đó không đọc được key trong `.env` khi chạy không có `--env-file`, nên tôi thêm `load_dotenv()` ở [app/main.py](../app/main.py).
- **Cách hiểu luồng Metrics → Logs → Traces:** metrics (dashboard 6 panel) trả lời *có vấn đề gì và từ lúc nào*, ví dụ P95 vượt 3000ms từ phút X. Logs trả lời *request nào bị ảnh hưởng*: lọc `data/logs.jsonl` theo khoảng thời gian và điều kiện (`latency_ms > 3000`, `event=request_failed`) để lấy `correlation_id`. Traces trả lời *bước nào gây ra*: tìm trace có metadata `correlation_id` đó, so thời gian và trạng thái của span `retrieval` với `llm-generate`. Span bất thường chính là root cause cần sửa. `correlation_id` là khóa nối cả ba lớp, nên phải được sinh ở middleware và gắn vào cả log lẫn trace.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** với LLM, thay prompt cũng là một lần deploy: nó có thể đổi chất lượng, độ dài output và chi phí mà không đổi dòng code nào. Vì vậy prompt cần version và label. App lấy prompt theo label `production`, nên promote hay rollback chỉ là chuyển label trên Langfuse, có hiệu lực ngay mà không cần deploy lại. Token/cost trên từng generation cho biết một prompt version có làm `tokens_out` tăng hay không (alert `daily_cost_spike`). SLO và error budget là căn cứ để quyết định: còn budget thì thử candidate, cháy budget thì rollback và ưu tiên độ ổn định.
- **Điều quan trọng nhất đã học:** observability chỉ có giá trị khi ba nguồn dữ liệu nối được với nhau bằng cùng một ID, và khi dữ liệu an toàn để chia sẻ. Vì vậy PII phải được scrub ngay trong pipeline logging (trước renderer/file writer), không để đến lúc đọc log mới xử lý.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - LLM là mock (`app/mock_llm.py`): `tokens_out` và `quality_score` sinh theo heuristic, nên chưa so sánh được chất lượng thật giữa prompt v1 và v2, chỉ so được `tokens_in` và cost.
  - Dashboard ([11](evidence/11-dashboard-overview.png)) là HTML tĩnh render từ `data/logs.jsonl` bằng [scripts/render_dashboard.py](../scripts/render_dashboard.py), chưa phải Grafana/Langfuse dashboard live; alert rules trong [config/alert_rules.yaml](../config/alert_rules.yaml) chưa được nối vào một alert manager chạy thật.
  - Ngưỡng `high_latency_p95` (3000ms) không bắt được incident `rag_slow` (P95 2667ms), như đã phân tích ở mục 7; alert riêng cho span retrieval mới chỉ là đề xuất.

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
