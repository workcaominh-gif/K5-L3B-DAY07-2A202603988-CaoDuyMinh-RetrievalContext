# Day 7 — Retrieval & Context Engineering · Cao Duy Minh · 2A202603988 · L3B

Báo cáo: [report/individual/2A202603988_CaoDuyMinh.md](report/individual/2A202603988_CaoDuyMinh.md) ·
Cấu hình chốt: [eval/LOCKED.md](eval/LOCKED.md) · Kết quả: [eval/results/](eval/results/)

## Hai phần

| Phần | Kho dữ liệu | Nội dung |
|---|---|---|
| **Bài cơ bản (rubric 85 điểm)** | Vector store Day 6: EU AI Act + GDPR, 572 trang, Postgres/pgvector | 6 phương pháp retrieval trên cùng 24 câu Day 6 + 4 câu thiếu bằng chứng (dev 18+2, test 6+2); agent Claude Sonnet 5.5 ReAct có guardrails; baseline vs cấu hình chọn trên dev và test |
| **Thử thách nâng cao (+15)** | Dietary Guidelines for Americans 2020–2025 (USDA+HHS, 164 trang, bảng + biểu đồ + ảnh) | Pipeline trích xuất có kiểm chứng (`parser/DGA_PIPELINE.md`), benchmark dev 22 / test 30 (`benchmark/dga/`), cấu hình chốt trên dev (`eval/DGA_LOCKED.md`), test duyệt tay **29/30 = 96,7%** (`eval/results/dga/REVIEW_test.md`) |
| **Mở rộng (demo)** | Sách USDA 148 trang + 2 video YouTube (public domain) | Pipeline nạp đa phương thức theo slide 7 (Data → Processing → Indexing → Enrichment → Compilation), agent đa phương thức (chữ, ảnh, giọng nói, Shazam, ngân nga), web 7 tab |

## Chạy lại

**Dựng lại vector store (nếu chưa có Day 6):** clone repo public
[K5-L3B-DAY06-2A202603988-DataIngestion](https://github.com/workcaominh-gif/K5-L3B-DAY06-2A202603988-DataIngestion) đặt cạnh
thư mục này (`AI20K/Day 6/…` và `AI20K/Day 7/…`), làm theo phần "Cài đặt và chạy" của README Day 6: tạo venv, `.env` từ `.env.example`,
`docker compose -p day6_student_starter up -d --wait`, đặt 2 PDF theo `data/manifest.json` (nguồn công khai, không commit), rồi
`python -m src.run ingest` → bảng `chunks_bge` / `chunks_gemma` (chunking B) mà Day 7 dùng. Không cần chạy lại `llm` (đã cache).

Yêu cầu: Postgres/pgvector của Day 6 đang chạy (`docker start day6_student_starter-postgres-1`), venv Day 6 (có torch,
sentence-transformers, rank_bm25, anthropic), `ANTHROPIC_API_KEY` trong `.env` của Day 6 (không có trong repo này).

```bash
PY="../../Day 6/K5-L3B-DAY06-2A202603988-DataIngestion/starter/.venv/bin/python"
"$PY" eval/run_day6.py --split dev          # 6 phương pháp retrieval, Hit@1 / Evidence Hit@3 / MRR@10
"$PY" eval/agent_day6.py --config gemma --split dev   # agent, cấu hình chọn  (bge = baseline)
"$PY" eval/score_agent.py                   # tổng hợp nhãn -> starter/agent_metrics.py
python3 -m unittest discover -s tests -v    # test của đề (15 test)
"$PY" app/server.py                         # demo http://127.0.0.1:8780
```

Pipeline mở rộng (dữ liệu thô và chỉ mục nằm trên ổ ngoài `/Volumes/T7 Dev/AI20K/day7/`, không commit):
`parser/prepare_pages.py` → agent VLM theo `parser/VLM_PAGE_SPEC.md` → `parser/verify_numbers.py` → `parser/enrich.py`
→ agent biên soạn theo `parser/COMPILE_SPEC.md` → `parser/index_kb.py`, `parser/mm_search.py index`, `parser/gemma_index.py build`,
`parser/audio_search.py build`, `parser/dense_frames.py`, `parser/pdf_images.py`. Mô tả: `parser/PIPELINE.md`.

Không có secret trong repo: `.env` bị gitignore; khoá API đọc từ `.env` của Day 6 lúc chạy.
