# Alert và Runbook

Mỗi alert dựa trên triệu chứng người dùng hoặc SLO, không dựa trên tên implementation nội bộ. Cấu hình máy đọc: [config/alert_rules.yaml](../config/alert_rules.yaml).

## Alert 1

- Tên: high_latency_p95
- Severity: P2
- Duration: 5m
- Kênh thông báo: Slack (#day13-alerts)
- SLI/SLO liên quan: fast_successful_requests (latency ≤ 2000ms, target 99.5%)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 2000 on response_sent` liên tục trong 5m
- Ảnh hưởng tới người dùng: Người dùng chờ > 2s; nguy cơ đốt error budget nhanh.
- Ba bước kiểm tra đầu tiên: 1) Dashboard panel Latency: xác nhận P95/TTFT tăng. 2) Lọc data/logs.jsonl theo latency_ms > 2000, lấy correlation_id. 3) Mở trace cùng correlation_id, xem span retrieval vs llm-generate.
- Mitigation tạm thời: Tắt tính năng chậm/incident (rag_slow), scale hoặc rollback prompt production.
- Owner: on-call-backend

## Alert 2

- Tên: high_error_rate
- Severity: P1
- Duration: 5m
- Kênh thông báo: Slack (#day13-alerts)
- SLI/SLO liên quan: Guardrail error_rate_pct_max=2 và retrieval_success_rate_pct_min=90
- Điều kiện và thời gian duy trì: `error_rate_pct > 2 (request_failed / request_received)` liên tục trong 5m
- Ảnh hưởng tới người dùng: Request trả HTTP 500, người dùng không nhận được câu trả lời.
- Ba bước kiểm tra đầu tiên: 1) Panel Errors: xem error_type và tool_success_rate. 2) Lọc log event=request_failed, lấy correlation_id. 3) Mở trace, tìm span retrieval lỗi (Vector store timeout).
- Mitigation tạm thời: Failover vector store / dùng fallback answer, disable incident tool_fail, rollback deploy.
- Owner: on-call-backend

## Alert 3

- Tên: daily_cost_spike
- Severity: P3
- Duration: 15m
- Kênh thông báo: Slack (#day13-alerts)
- SLI/SLO liên quan: Guardrail daily_cost_usd_max=2.5
- Điều kiện và thời gian duy trì: `sum(cost_usd) > 2.5 per day hoặc tokens_out tăng > 3x baseline` liên tục trong 15m
- Ảnh hưởng tới người dùng: Không ảnh hưởng trực tiếp người dùng nhưng đốt ngân sách.
- Ba bước kiểm tra đầu tiên: 1) Panel Cost/Tokens: xác định phút tăng. 2) Lọc log response_sent có tokens_out cao, lấy correlation_id. 3) Trace generation: kiểm tra usage, model, prompt version.
- Mitigation tạm thời: Giới hạn max_tokens, rollback prompt version gây dài, tắt cost_spike.
- Owner: on-call-llmops
