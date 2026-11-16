# Báo cáo Day 7 — Cao Duy Minh · 2A202603988 · L3B

Tóm tắt: trên vector store Day 6 (EU AI Act + GDPR), tôi so 6 phương pháp retrieval trên cùng bộ câu hỏi, chốt cấu hình
trên dev (`eval/LOCKED.md`) rồi mới chạy test, và đánh giá agent Claude Sonnet 5.5 (ReAct, guardrails) cho baseline và
cấu hình chọn. Phần mở rộng là một kho đa phương thức (sách PDF 148 trang + 2 video) với agent tìm bằng chữ, ảnh, giọng nói
và âm thanh — trình bày ở cuối, **không** dùng để tính điểm phần cơ bản.

## Dữ liệu và benchmark

- **Nguồn, quyền, số trang, số chunk:** EU AI Act (bản Nghị viện thông qua, 2024) và GDPR (Regulation 2016/679), văn bản
  chính thức của EU, dùng cho học tập; 572 trang. Index Day 6, chunking B (theo cấu trúc Điều/khoản/phụ lục, có header ngữ
  cảnh) = 1.212 chunk. Câu hỏi nêu phạm vi (recital/annex) được lọc `part` trong SQL (cấu hình C của Day 6).
- **Vector store, embedding:** PostgreSQL 16 + pgvector (exact cosine, lọc trước). Baseline `BAAI/bge-small-en-v1.5`
  (384 chiều, bảng `chunks_bge`); cấu hình chọn `google/embeddinggemma-300m` (768 chiều, bảng `chunks_gemma`) — cả hai
  vector đã có từ Day 6, không tạo lại index. Query embedding dùng đúng model và prompt của index tương ứng.
- **Agent:** Claude Sonnet 5.5 (`claude-sonnet-5-5`), adaptive thinking, effort medium; tool `search_law(query, part?, top_k?)`
  và `read_chunk(chunk_id)`. Chạy: `eval/agent_day6.py --config {gemma|bge} --split {dev|test}`.
- **Benchmark (`benchmark/day6_eu/questions.jsonl`):** 24 câu có đáp án của Day 6 (dev 18 / test 6; mỗi câu có nguồn, trang,
  câu trích bằng chứng; loại direct / paraphrase / condition / exception / filter / version) + **4 câu thiếu bằng chứng**
  mới (dev 2 / test 2), gần chủ đề: phí đăng ký GDPR, số nhân sự AI Office, án phạt của DPC Ireland với Meta, số tiền EU cho
  mỗi sandbox. Mỗi câu thiếu bằng chứng được kiểm tra trên toàn bộ 572 trang bằng regex (0 kết quả; regex đối chứng
  "reasonable fee" tìm được 3 trang, chứng tỏ cách kiểm tra hoạt động) — lý do ghi trong `absence_reason`.
- **Tiêu chí chấm:** HIT = đúng tài liệu + khoảng trang chứa trang gold + chunk chứa **trọn** câu trích bằng chứng
  (`evaluation.is_hit` của Day 6, dùng nguyên). Test Day 6 chưa từng dùng để chỉnh; Day 7 chốt cấu hình trước khi chạy test.

## Retrieval và thử nghiệm

| Cấu hình | Phương pháp, top-k, filter, rerank, context | Giả thuyết / thay đổi | Split | Hit@1 | Evidence Hit@3 | MRR@10 | Thời gian / chi phí |
|---|---|---|---|---|---|---|---|
| Baseline | Dense bge-small, top-3, lọc `part` khi câu hỏi nêu phạm vi | Cấu hình Day 6 | dev | 8/18 | 14/18 | 0.616 | 10.5 s · $0 |
| Phương pháp 2 | BM25 (Okapi, rank_bm25) trên cùng chunk, cùng filter | Từ khoá luật (số Điều, thuật ngữ) giúp | dev | 8/18 | 10/18 | 0.507 | 0.1 s · $0 |
| Phương pháp 3 | Hybrid RRF(dense top-30, BM25 top-30), k=60 | Gộp nghĩa + từ khoá | dev | 8/18 | 12/18 | 0.594 | 0.6 s · $0 |
| Cải thiện 1 | Hybrid top-20 → **rerank Claude Haiku 5.5** (chấm 0–3, JSON schema) | Bằng chứng có trong ứng viên nhưng xếp thấp | dev | **14/18** | 15/18 | 0.817 | 56.5 s · $0.011 |
| Cải thiện 2 | **Query transformation**: Haiku 5.5 viết 3 truy vấn (thuật ngữ luật / mở rộng / tách ý), hybrid mỗi truy vấn, RRF | Câu hỏi đời thường lệch từ vựng luật | dev | 13/18 | **18/18** | **0.861** | 39.9 s · $0.0023 |
| Cải thiện 3 (đổi model) | Dense **EmbeddingGemma-300m** (index Day 6) | Model embedding tốt hơn bắt được diễn đạt lại | dev | 12/18 | **18/18** | 0.824 | 6.0 s · $0 |
| **Cấu hình đã chọn** | Dense EmbeddingGemma-300m | Chốt trên dev (`eval/LOCKED.md`) | test | 2/6 | 4/6 | 0.556 | 4.3 s · $0 |
| Baseline | Dense bge-small | — | test | 2/6 | 4/6 | 0.542 | 8.4 s · $0 |
| (tham khảo) | Query transformation | không được chọn | test | 4/6 | 6/6 | 0.806 | 14.6 s · $0.0008 |
| (tham khảo) | Hybrid + rerank | không được chọn | test | 4/6 | 5/6 | 0.722 | 17.1 s · $0.0035 |

Lệnh: `eval/run_day6.py --split dev|test`; kết quả và top-3 từng câu: `eval/results/day6_{dev,test}.json`.

**Tiêu chí chọn (đặt trước):** (1) Evidence Hit@3 dev, (2) MRR@10, (3) thời gian/chi phí và số điểm lỗi. Gemma và rewrite
cùng 18/18; Gemma kém MRR 0.037 nhưng nhanh hơn ~7 lần, không cần gọi LLM → chọn Gemma. **Trên test, cấu hình chọn không
tốt hơn baseline (4/6 = 4/6), còn rewrite đạt 6/6.** Tôi giữ nguyên lựa chọn và báo cáo đúng như vậy (không chỉnh sau khi
xem test); với n = 6 chênh lệch là 2 câu, nhưng nó cho thấy lựa chọn trên 18 câu dev chưa đủ chắc.

**Hai lỗi dev, nguyên nhân, thử nghiệm:**
1. **q05 (paraphrase, data portability):** "lấy lại dữ liệu để chuyển sang dịch vụ khác" không chứa từ "portability" hay
   "structured, commonly used and machine-readable format"; bge trả recital chung (tr. 27, 17, 82). Rerank **không** cứu
   được vì chunk bằng chứng không có trong 20 ứng viên → lỗi nằm ở bước truy hồi, không ở xếp hạng. Rewrite (Haiku dùng
   thuật ngữ luật) đưa lên hạng 2; Gemma lên hạng 1.
2. **q12 (bẫy chủ đề):** "mức phạt tối đa cho hành vi AI bị cấm" kéo về Điều 5 (danh sách hành vi bị cấm, tr. 181) thay vì
   Điều 99 về chế tài (tr. 391). Rewrite thêm "penalties / administrative fines / Article 99" → hạng 2; rerank lại không cứu
   được (ứng viên không có Điều 99). Ngược lại **q16** (nghĩa vụ hiểu biết AI) bằng chứng đã ở hạng 10 → rerank đưa lên hạng 1.
   Kết luận: rerank sửa lỗi *xếp hạng*, rewrite/model tốt sửa lỗi *truy hồi*.

**Đánh đổi:** BM25 và hybrid **tệ hơn** dense trên kho luật này (từ khoá chung như "AI", "data", "processing" xuất hiện khắp
nơi); rerank cho Hit@1 tốt nhất nhưng chậm nhất (~3 s/câu, có chi phí); rewrite rẻ (~$0.0001/câu) và đạt Evidence Hit@3 cao
nhất cả dev lẫn test.

## Agent và đánh giá

- **Tool, lượt gọi, điều kiện dừng, context, lỗi:** 2 tool trong allowlist, kiểm tham số theo JSON schema; ngân sách 8 vòng /
  24 lời gọi mỗi câu (agent của web demo có thêm trần 60k token, chống gọi lặp cùng tham số và chống lặp câu trả lời). Context
  = các chunk tool trả về (top-5, tối đa 900 ký tự/chunk) bọc `<untrusted_data>`, cụm câu dạng chỉ dẫn bị vô hiệu hoá.
  Điều kiện dừng: model trả lời (stop_reason end_turn) hoặc hết ngân sách. Guardrail đầu ra: mọi `[cite:id]` phải là chunk được
  trả về trong lượt; citation lạ bị xoá và đánh dấu "không có nguồn"; câu trả lời không còn citation hợp lệ → từ chối. Lỗi
  provider/kho được ghi riêng (`status: error`), không thay bằng kết quả giả (0 lỗi trong 56 lượt).

| Cấu hình / split | Tool use | Số lượt tìm/câu | Grounded answer 0/1/2 · TB | Citation hợp lệ | Câu có citation | Abstention đúng | Từ chối nhầm | Context Evidence Rate | Chi phí · trung vị |
|---|---|---|---|---|---|---|---|---|---|
| Baseline bge / dev | 20/20 | 1.10 | 0/1/17 · 1.94 | 41/43 | 18/18 | 2/2 | 0/18 | 18/18 | $0.173 · 4.9 s |
| Chọn Gemma / dev | 20/20 | 1.05 | 0/0/18 · 2.00 | 44/44 | 18/18 | 2/2 | 0/18 | 18/18 | $0.186 · 5.2 s |
| Baseline bge / test | 8/8 | 1.00 | 0/0/6 · 2.00 | 13/15 | 6/6 | 2/2 | 0/6 | 6/6 | $0.064 · 9.9 s |
| Chọn Gemma / test | 8/8 | 1.00 | 0/0/6 · 2.00 | 13/15 | 6/6 | 2/2 | 0/6 | 6/6 | $0.065 · 26.2 s |

Context Evidence Rate của agent (100%) cao hơn Evidence Hit@3 của một lượt retrieval vì agent tự viết truy vấn (đúng thuật ngữ
luật) và lấy top-5 — tức agent đã làm phần "query transformation" ngay trong vòng ReAct. Trên kho này, cả hai cấu hình agent
cho chất lượng trả lời gần như như nhau; khác biệt nằm ở retrieval một lượt.

**Nhãn:** bản nháp do Claude Haiku 5.5 làm giám khảo (được xem đáp án và câu trích gold — chỉ để *chấm*, agent không bao giờ
thấy) + gợi ý xác định (chunk được trích có chứa trọn câu bằng chứng không). **Tôi đọc toàn bộ 16 dòng test** (6 có đáp án +
2 thiếu bằng chứng × 2 cấu hình) đối chiếu với văn bản; sửa 1 nhãn: bge/q09 giám khảo chấm 1 vì cho rằng "nghĩa vụ áp dụng
cho cả controller và processor" là sai — Điều 37(1) GDPR ghi đúng như vậy → chấm lại 2 (`eval/results/manual_review_test.json`).
Tổng hợp bằng `starter/agent_metrics.py` của đề (`eval/score_agent.py`).

| Query ID | Loại câu | Tool call và kết quả | Câu trả lời và citation | Nhãn, lý do |
|---|---|---|---|---|
| q04 (test, Gemma) | paraphrase | 1× search_law → gdpr Điều 12(3) | 1 tháng, gia hạn 2 tháng nếu phức tạp/nhiều yêu cầu, phải báo trong tháng đầu `[cite:B:gdpr-2016:233]` | 2 — đủ thời hạn và điều kiện gia hạn |
| q23 (test, Gemma) | version | 1× search_law → AI Act Điều 113 | Áp dụng 24 tháng sau khi có hiệu lực; văn bản chỉ có chỗ trống "[24 months…]", không có ngày cụ thể `[cite:B:eu-ai-act-2024:690]` | 2 — tránh được bẫy phiên bản (Day 6 mọi cấu hình đều trượt câu này ở mức retrieval) |
| u03 (test, Gemma) | thiếu bằng chứng | 1× search_law → recital 148 về phạt hành chính | "Not enough evidence…": kho chỉ có văn bản luật, không có quyết định xử phạt | Từ chối đúng; citation recital 148 bị giám khảo coi là không hỗ trợ (bảo thủ, giữ nguyên) |
| q09 (test, bge) | condition | 1× search_law → GDPR Điều 37 | DPO bắt buộc khi cơ quan công quyền xử lý, trừ toà án khi xét xử `[cite:B:gdpr-2016:305]` | 2 (sửa từ 1, xem trên); citation thứ hai (chunk 306) không hỗ trợ |
| q19 (test, Gemma) | filter (annex) | 1× search_law part=annex → Phụ lục III điểm 3 | 4 ứng dụng giáo dục rủi ro cao `[cite:…701][cite:…702]` | 2; citation 700 (đầu Phụ lục III) thừa → không hỗ trợ |

- **Trace, nhãn, lệnh, thời gian, chi phí:** `eval/results/agent_<cfg>_<split>.json` (sự kiện từng lượt: thought, search với
  query/filter/kết quả, read; context_ids; câu trả lời gốc và sau guardrail), `reviews_*`, `metrics_*`, `manual_review_test.json`.
  Tổng chi phí agent 56 lượt ≈ $0.49; giám khảo ≈ $0.013; retrieval benchmark ≈ $0.018.
- **Giới hạn:** test chỉ 6 câu có đáp án → khoảng tin cậy rất rộng; nhãn chất lượng trả lời là nháp do LLM + tôi đọc lại test
  (dev chưa đọc tay hết); Context Evidence Rate dùng tiêu chí "chunk chứa trọn câu trích" nên không ghi nhận bằng chứng diễn đạt khác.

## Phần mở rộng: Kitchen KB đa phương thức (demo, không tính vào rubric cơ bản)

Nguồn: *Recipes for Healthy Kids: Cookbook for Child Care Centers* (USDA FNS 2013, 148 trang, public domain) + 2 video USDA
Team Nutrition trên YouTube. Pipeline theo slide 7 (Data → Processing → Indexing → Enrichment → Compilation → Storage → RAG →
Interface), mô tả trong `parser/PIPELINE.md`:

- **Processing:** triage trang; 5 agent Sonnet 5.5 + 3 agent Haiku 5.5 chuyển 148 trang (bảng nguyên liệu, nhãn dinh dưỡng là
  ảnh, ảnh full-bleed, mục lục) thành HTML giữ bố cục + 2.600 fact nguyên tử; **5.443 con số được đối chiếu tự động với text
  layer PDF** sau khi giải mã font phân số (K=½ … V=⅛, do agent phát hiện), 7 lệch đều vô hại, 16 chỉ có trong ảnh. Video:
  yt-dlp, Whisper (local), phụ đề, khung hình mỗi giây + OCR, 2 agent Sonnet gộp thành đoạn có mốc thời gian; thời điểm từng
  nguyên liệu trên thẻ được OCR xác minh tới từng giây.
- **Enrichment/Compilation:** metadata, dị ứng (theo tên nguyên liệu), CCP, graph 551 cạnh; wiki 30 món, SOP an toàn thực phẩm,
  FAQ 48 câu, glossary — đều có trích dẫn trang/mốc video.
- **Tìm kiếm đa phương thức:** chữ (EmbeddingGemma 2 — thắng trên FAQ 48 câu: Hit@1 43/48 so với 28/48 của hybrid bge), ảnh
  (CLIP + EmbeddingGemma 2 + OCR + dHash + template matching cho ảnh cắt nhỏ; 151 hình nhúng trong PDF được index riêng),
  vân âm thanh kiểu Shazam (100% với đoạn 3–10 s sạch và SNR 10 dB), giọng nói (Whisper), ngân nga (pYIN + DTW; chỉ đáng tin
  với đoạn có nhạc). Kết quả trong `eval/results/kitchen/`.
- **Agent và giao diện:** Claude Sonnet 5.5 ReAct với 8 tool (thêm `view_candidates` cho model tự nhìn ảnh, `get_recipe` để kiểm
  chứng), verifier tự sửa (tối đa 2 lần), prompt caching + cache câu trả lời, web 9 tab (Agent, PDF ↔ kết quả, trang khó → HTML, kho vector, so sánh truy xuất,
  dữ liệu đã nạp, Graph, Pipeline).
- **Thử thách nâng cao (+15):** **không đăng ký.** Sách không có biểu đồ (yêu cầu ≥ 5 câu biểu đồ) và chưa có test 30 câu chấm
  tay theo `ADVANCED.md`.

## Tái lập

`STUDENT.md` có lệnh chạy. Phụ thuộc: Postgres/pgvector Day 6 đang chạy, venv Day 6 (torch, sentence-transformers,
rank_bm25, anthropic), `ANTHROPIC_API_KEY` trong `.env` của Day 6 (không có trong repo). Test của đề: 15/15 pass.
