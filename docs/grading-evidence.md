# Evidence dùng để chấm bài

Danh sách chính thức, quy tắc chụp và cách nộp nằm tại [SUBMISSION.md](SUBMISSION.md). File này là checklist nhanh khi bạn thu thập evidence cá nhân.

## Evidence runtime bắt buộc

- [x] Kết quả cuối của `python -m pytest -q`. → `evidence/01-pytest.txt` (32 passed)
- [x] `validate_logs.py` đạt tối thiểu 80/100. → `evidence/02-log-validator.txt` (100/100)
- [x] `validate_dashboard.py` đạt 6/6. → `evidence/03-dashboard-validator.txt`
- [x] Structured log có `correlation_id` và metadata. → `evidence/04-structured-log.png|.txt`
- [x] PII giả đã được redact trong output thực tế. → `evidence/05-pii-redaction.png|.txt`
- [x] Tên project Langfuse cá nhân và danh sách tối thiểu 10 traces do học viên tự tạo. → `evidence/06-trace-list.png` (`day13-k4-l3a-02515`, 12 traces)
- [x] Một trace waterfall có root, retrieval và generation. → `evidence/07-trace-waterfall.png|.txt`
- [x] Trace metadata có correlation ID, prompt version/label, token và cost. → `evidence/08-trace-metadata.png`
- [x] Prompt v1/v2 và bằng chứng promote/rollback. → `evidence/09-prompt-versions.png`, `evidence/10-prompt-rollback.png`
- [x] Dashboard runtime đủ 6 panel, time range, đơn vị và threshold. → `evidence/11-dashboard-overview.png`
- [x] Incident metric, incident log và incident trace nối được bằng cùng correlation ID/khoảng sự cố. → `evidence/12-incident-metric.*`, `evidence/13-incident-log.*`, `evidence/14-incident-trace.*` (`req-4c129a7d`, 09:05:13–09:05:27Z)

## Artifact kiểm tra trực tiếp trên repo

Không cần chụp toàn bộ code. Dẫn link tới:

- `config/slo.yaml` và phần giải thích error budget trong `submission/REPORT.md`;
- `config/alert_rules.yaml` và `docs/alerts.md`;
- source, tests và commit history;
- `submission/REPORT.md`.

## Chất lượng evidence

- Evidence phải thuộc commit SHA được nộp và đúng challenge của lớp.
- Ảnh phải đọc được thông tin dùng để chấm, không phải ảnh trang trống.
- Che secret và PII; không dùng dữ liệu thật.
- Trace/prompt phải thuộc project cá nhân `day13-k4-l3a-<MSSV>`; không chụp trang API Keys.
- Đặt file trong `submission/evidence/`.
- Dẫn đường dẫn tương đối từ report, ví dụ `evidence/07-trace-waterfall.png`.
- Metric, log và trace của incident phải cùng chỉ về một nguyên nhân.
