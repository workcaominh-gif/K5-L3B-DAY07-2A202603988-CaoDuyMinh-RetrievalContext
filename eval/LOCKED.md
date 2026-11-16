# Cấu hình đã chốt trên dev (trước khi chạy test)

Ngày chốt: 2026-11-16, sau `eval/run_day6.py --split dev` (kết quả: `eval/results/day6_dev.json`).
Test **chưa** được chạy khi chốt; không chỉnh gì sau khi xem test.

## Tiêu chí chọn (đặt trước, theo thứ tự ưu tiên)
1. Evidence Hit@3 trên dev (câu có đáp án) — evidence phải nằm trong context agent nhận được.
2. MRR@10 (thứ hạng của chunk bằng chứng).
3. Thời gian và chi phí mỗi câu (ưu tiên không phụ thuộc thêm một lời gọi LLM).

## Kết quả dev (18 câu có đáp án)
| Phương pháp | Hit@1 | Evidence Hit@3 | MRR@10 | Thời gian | Chi phí Claude |
|---|---|---|---|---|---|
| dense (bge-small, Day 6) — baseline | 8 | 14 | 0.616 | 10.5 s | $0 |
| bm25 | 8 | 10 | 0.507 | 0.1 s | $0 |
| hybrid RRF | 8 | 12 | 0.594 | 0.6 s | $0 |
| hybrid + rerank Haiku 5.5 | 14 | 15 | 0.817 | 56.5 s | $0.011 |
| query rewrite (Haiku 5.5, 3 truy vấn, RRF) | 13 | 18 | 0.861 | 39.9 s | $0.0023 |
| dense EmbeddingGemma-300m (Day 6 store) | 12 | 18 | 0.824 | 6.0 s | $0 |

## Quyết định
- **Cấu hình chọn: dense EmbeddingGemma-300m** (bảng `chunks_gemma`, chunking B, lọc `part` khi câu hỏi nêu phạm vi).
  Lý do: đạt mức cao nhất ở tiêu chí 1 (18/18, hoà với rewrite); tiêu chí 2 kém rewrite 0.037 nhưng tiêu chí 3 tốt hơn rõ
  (6 s so với 40 s, không cần gọi LLM, không thêm điểm lỗi).
- **Baseline: dense bge-small** (cấu hình Day 6 đã chọn).
- Hai cấu hình cải thiện được đo riêng (giả thuyết ghi trong báo cáo): hybrid + rerank, query rewrite.
- Agent (Claude Sonnet 5.5) dùng cấu hình đã chọn làm công cụ tìm kiếm; baseline agent dùng dense bge-small.
