# Pipeline ingest + index: Dietary Guidelines for Americans 2020–2025 (thử thách nâng cao)

## 1. Tài liệu nguồn

| | |
|---|---|
| Tên | *Dietary Guidelines for Americans, 2020–2025*, ấn bản thứ 9 (tháng 12/2020) |
| Cơ quan | U.S. Department of Agriculture (USDA) & U.S. Department of Health and Human Services (HHS) |
| Bản gốc | https://www.dietaryguidelines.gov/sites/default/files/2020-12/Dietary_Guidelines_for_Americans_2020-2025.pdf |
| File dùng | `/Volumes/T7 Dev/AI20K/day7/dga/raw/dga_2020_2025.pdf` — 164 trang PDF, 612×792 pt; sha256 bắt đầu bằng `ceea04ce1a7c13a9` |
| Quyền sử dụng | Tác phẩm của chính phủ liên bang Mỹ → public domain (17 U.S.C. §105), được phép sao chép/xử lý |
| Số trang | Số trang in ≠ số trang PDF (PDF p.90 = "Page 77"). Mọi unit lưu **cả hai**: `pdf_page` và `printed_page` |

Nội dung: text (5 chương + phụ lục), ~32 bảng (Appendix 1 nutrient goals, Appendix 3 food patterns theo mức calo),
58 vùng biểu đồ (dot-range "Average Intakes vs Recommended Intake Ranges", donut % vượt giới hạn, bar chart),
~164 ảnh/infographic/diagram.

## 2. Các bước và lệnh tái lập

Python: `"/Volumes/T7 Dev/AI20K/day6/venv/bin/python"`, env `HF_HOME="/Volumes/T7 Dev/AI20K/day6/hf_cache" HF_HUB_OFFLINE=1`.
`ANTHROPIC_API_KEY`, `DATABASE_URL` lấy từ `Day 6/.../starter/.env` (Postgres 16 + pgvector, container
`day6_student_starter-postgres-1`, cổng 55433). Render trang (150 dpi PNG + text layer) có sẵn ở `work/pages/pNNN.{png,txt}`.

```bash
PY="/Volumes/T7 Dev/AI20K/day6/venv/bin/python"
export HF_HOME="/Volumes/T7 Dev/AI20K/day6/hf_cache" HF_HUB_OFFLINE=1
$PY parser/dga_extract.py triage                 # Sonnet/Haiku split -> work/triage.json
$PY parser/dga_extract.py run                    # 164 trang, 6 luồng, cache work/json/pNNN.json (~5 phút)
$PY parser/dga_verify.py                         # kiểm tra số + hình học biểu đồ -> work/verify.json
$PY parser/dga_verify.py --fix 8                 # (tuỳ chọn) chạy lại trang có >=3 số in sai, kèm corrective note
$PY parser/dga_index.py build                    # crops + units + embeddings -> bảng dga_units (~4 phút; lần đầu ~9 phút)
$PY parser/dga_index.py stats                    # -> work/stats.json
$PY parser/dga_search.py "red and orange vegetables at 2,000 calories" hybrid 5
$PY parser/dga_search.py --region dga:p090:r1    # dữ liệu vùng + crop
```
Các lần chạy lại sửa lỗi đã dùng (xem mục 5):
```bash
$PY parser/dga_extract.py run 91,93,99,111 --force --note "<note về số cột dot-range>"
# 19,45,47,62,70,75,81,103,117: chạy lại bằng Sonnet với note "trang text thiếu facts" (E.extract(n, E.SONNET, note))
```
Mọi bước idempotent: JSON cache theo trang, index delete+insert theo `id` (và xoá id không còn tồn tại), vector ảnh
của crop/trang không đổi được tái sử dụng từ DB (`--reembed-images` để ép tính lại).

## 3. Trích xuất (parser/dga_extract.py)

- **Một call Claude / trang**: ảnh trang (JPEG, cạnh dài ≤1600 px) + text layer của trang + spec; output có cấu trúc
  qua `output_config.format = json_schema`: `printed_page, section, html, facts[], regions[{id, kind, title, bbox_norm,
  summary, alt, data{header, rows, chart_type, x_axis, y_axis, series, points[{series, category, value, unit, source}],
  elements}}], confidence, illegible[]`.
- **Nguyên tắc**: text layer là nguồn chuẩn cho ký tự in (số, chữ); ảnh dùng cho bố cục, cấu trúc bảng, hình học biểu
  đồ, ảnh chụp. Mỗi điểm biểu đồ ghi `source = printed | read_off_axis`. Fact phải tự đủ nghĩa (chủ thể, nhóm tuổi/giới,
  mức calo, giá trị + đơn vị, nguồn bảng/hình).
- **Triage**: Sonnet 5.5 (effort medium) nếu trang có ≥100 vector drawing (PyMuPDF `get_drawings`) hoặc có dòng bắt đầu
  bằng caption `Figure N-N` / `Table AN-N`; còn lại Haiku 5.5 (effort low). (Quy tắc ban đầu "có ảnh raster / có chữ
  Table" đẩy 149/164 trang sang Sonnet vì ảnh trang trí và tham chiếu trong văn bản — đã siết lại.) Kết quả: 70 Sonnet
  / 94 Haiku; sau khi chạy lại 9 trang text bằng Sonnet: 79 / 85.
- Tinh chỉnh prompt sau 3 trang mẫu (p.90 chart, p.157 bảng A3-2, p.31 text): (1) tiêu đề panel phải có số hình + tên
  hình ("Figure 3-2. Current Intakes: Ages 2 Through 4 - …") vì một Figure có nhiều panel; (2) dot-range phải liệt kê
  đầu low/high cho **mọi** cột M/F (lần đầu model bỏ các cột trùng giá trị).
- Retry 4 lần với backoff; log token + chi phí từng call ở `work/extract_log.jsonl`.

## 4. Kiểm chứng (parser/dga_verify.py) — kết quả

**(a) Số in so với text layer** (chuẩn hoá: bỏ dấu phẩy hàng nghìn, `1 ½` = `1½`, `1/2` = `½`):

| Loại | Đã kiểm | Có trong text layer |
|---|---|---|
| Ô bảng | 3 182 | 3 182 (100%) |
| Nhãn biểu đồ `printed` | 171 | 171 (100%) |
| Số trong facts | 6 374 | 6 176 (96.9%) |

Số trong facts không khớp chủ yếu là nội dung chỉ có trong ảnh (nhãn Nutrition Facts mẫu p.61, ảnh), giá trị ước lượng
từ biểu đồ ("khoảng 18%" ở Figure 1-6 p.43), hoặc số viết lại (ví dụ "2 ½" từ "2½ cup"). Bản ghi từng số ở
`work/verify.json → pages.<n>.numbers.mismatches`.

**(b) Hình học vector của biểu đồ**: với mọi vùng chart có điểm `read_off_axis`: tìm cột nhãn tick số thẳng đứng trong
vùng (`get_text("dict")`), hồi quy y→giá trị; lấy chấm (path tô màu gần vuông, rộng <13 pt) và thanh range (path cùng
bề rộng 8–25 pt; mép dưới/trên = low/high) từ `get_drawings()`; gom cột theo x; ánh xạ theo thứ tự vào category của model.
Đã kiểm chứng tay trên p.90: thanh Vegetables M = 1.00–2.00, chấm = 0.70 khớp hình.

| | |
|---|---|
| Vùng chart có điểm đọc từ trục | 37 |
| So sánh được | 36 (1 biểu đồ cột ngang p.43 Figure 1-6: không có trục dọc → không xử lý) |
| Điểm so sánh | 537, khớp 529 (98.5%, dung sai 0.2 × bước tick) |
| Điểm model bỏ sót, bổ sung từ hình học | 124 (`added_by: pdf_geometry`) |

Lỗi hệ thống phát hiện và đã sửa (không chỉ báo cáo):
1. 7 biểu đồ "Average Intakes of Subgroups" (p.91, 93, 99, 111) — model chỉ liệt kê 2–10 cột trong khi hình học có 6–12 cột
   → chạy lại 4 trang với corrective note nêu số cột; sau đó cả 7 khớp số cột.
2. Đầu range bị bỏ sót ở p.96, 113, 127, 140 → bổ sung trực tiếp giá trị hình học (124 điểm).
3. 9 trang text Haiku trả 0–1 fact (p.19, 45, 47, 62, 70, 75, 81, 103, 117) → chạy lại bằng Sonnet với note; nay 13–22 facts/trang.
4. Index dùng giá trị hình học khi có: dòng chart ghi "0.7 cup eq/day (read off axis; PDF vector-geometry value = 0.7)".

8 điểm lệch còn lại (p.79, 96, 99 r2, 139; lệch 0.2–0.37) để nguyên cả hai giá trị trong text của unit để agent thấy.

## 5. Crop và liên kết về bản gốc

Mỗi vùng table/chart/image/diagram → `work/crops/pNNN_rK.jpg` (từ render 150 dpi). bbox model (0–1) → PDF point → tinh
chỉnh bằng hợp các text block / drawing / ảnh có tâm nằm trong hộp (ngoại biên +3% trang), rồi kéo thêm caption
"Table …"/"Figure …" nằm ngay phía trên (≤70 pt). 254 crop, 183 được tinh chỉnh. `work/regions.json` lưu `bbox_pt`
(PDF point), `bbox_px_150dpi`, `bbox_norm_model`. Mọi unit có `pdf_page`, `printed_page`, `region`, `meta.crop`,
`meta.bbox_pt` → mở được đúng trang và vùng để kiểm chứng.

## 6. Index (parser/dga_index.py) — bảng `dga_units`

`dga_units(id text PK, kind, pdf_page int, printed_page text, region, title, text, meta jsonb, embedding vector(768), tsv tsvector)`,
GIN trên `tsv`, tìm kiếm vector chính xác (exact, 1 920 dòng nên không cần ivfflat).

| kind | Số dòng | Nội dung |
|---|---|---|
| page | 164 | header + tóm tắt các vùng + toàn bộ text trang (từ HTML) |
| chunk | 268 | đoạn ≤350 từ, header `Dietary Guidelines 2020-2025 · <chương> · p.<in> (PDF p.<n>)` |
| facts | 321 | nhóm ≤8 fact nguyên tử |
| table | 42 | tiêu đề + hàng tuyến tính "hàng \| cột: giá trị" (bảng dài tách ≤600 từ) |
| table_row | 457 | một hàng bảng / unit (trúng chính xác ô theo mức calo) |
| chart | 73 | tiêu đề + trục (nhãn, đơn vị, tick) + legend + mọi điểm dữ liệu (+ giá trị hình học) |
| image | 164 | ảnh/diagram: mô tả + alt + các nhãn |
| box | 13 | hộp callout |
| image:crop | 254 | embedding **ảnh** của crop |
| image:page | 164 | embedding **ảnh** của trang |

- Model: EmbeddingGemma 2 (`google/embeddinggemma-2`, Apache 2.0), 768-d, float32, L2-normalised, cosine. Text dùng
  prompt `Document`, truy vấn dùng `SearchQuery`, ảnh không prompt (theo model card); `max_seq_length = 1024`, batch 8
  (text) / 4 (ảnh) để tránh OOM trên MPS. Text và ảnh chung một không gian → câu hỏi bằng chữ có thể trúng hình.
- Full-text: `to_tsvector('english', title || text)`, số có dấu phẩy được thêm bản không dấu ("2,000" và "2000").

## 7. Tìm kiếm (parser/dga_search.py)

`search(query, method, k)` → `[{id, kind, pdf_page, printed_page, region, title, text, crop, bbox_pt, score}]`
- `lexical`: Postgres FTS, OR các từ (bỏ stopword), `ts_rank_cd`; chỉ unit text.
- `dense`: Gemma, chỉ unit text. `hybrid`: RRF(dense, lexical), k=60, 50 ứng viên mỗi danh sách.
- `dense_mm`: Gemma trên text + `image:crop` + `image:page`.
- `get_page(n)`: html, facts, danh sách vùng, ảnh trang, các unit. `get_region(id)`: dữ liệu vùng (hàng bảng / điểm
  biểu đồ kèm giá trị hình học / phần tử ảnh) + crop + bbox.

Kiểm thử nhanh: "red and orange vegetables per week at 2,000 calories" → `dense_mm` trả `table_row` hàng Red & Orange
của A3-x; "donut chart percent of teenage girls exceeding sodium limit" → các panel r3 của Figure 3-x;
"photo of a family eating dinner" → vùng ảnh. `lexical` (OR) thiên về unit `page` dài — nên dùng `hybrid`/`dense_mm`.

## 8. Thống kê (work/stats.json)

- 164/164 trang đã xử lý, 0 lỗi API; 180 call (164 + 16 chạy lại/mẫu).
- Token: 1 175 639 input / 446 937 output. Chi phí: Sonnet $4.05, Haiku $0.14, **tổng $4.19** (gồm cả chạy lại).
- Vùng: 145 image, 58 chart, 32 table, 19 diagram, 13 text-box; 1 986 facts; 1 920 unit.
- Thời gian: trích xuất ~5.5 phút (6 luồng), verify <10 s, index ~4 phút (lần đầu ~9 phút do embedding 412 ảnh).

## 9. Chưa xử lý / hạn chế và ảnh hưởng

| Phần | Lý do | Ảnh hưởng |
|---|---|---|
| p.163 | Trang trống (nền màu, không text layer) | Không có nội dung |
| Figure 1-6 (p.43, cột ngang chồng %) | Bộ đọc hình học chỉ hỗ trợ trục dọc | % là ước lượng của model ("about 18%"), không kiểm chứng được bằng hình học; câu hỏi cần số chính xác từ hình này có thể sai ±2–3 điểm % |
| Biểu đồ dot-range (9 trang, confidence 0.6) | Giá trị không in trên trang, chỉ có hình | Đã kiểm tra/bổ sung bằng hình học; còn 8/537 điểm lệch 0.2–0.37 |
| Donut charts | Chỉ lấy % in trên hình (đã khớp text layer 100%), không đo góc cung | Không ảnh hưởng (số đều được in) |
| Footnote của bảng nằm ngoài bbox model | bbox tinh chỉnh không mở rộng xuống dưới | Footnote vẫn có trong unit `page`/`chunk` nhưng không nằm trong crop |
| Ánh xạ cột hình học → category theo thứ tự trái→phải | Không đọc nhãn M/F theo vị trí | Nếu model liệt kê sai thứ tự, so sánh sẽ báo lệch (đã thấy 0 trường hợp số cột lệch sau khi sửa) |
| Facts chứa số không có trong text layer (3.1%) | Nội dung chỉ có trong ảnh hoặc là ước lượng | Không chặn index; được liệt kê trong verify.json để kiểm tra tay |
| Ảnh trang trí (ảnh minh hoạ người/thức ăn) | Chỉ mô tả ngắn | Ít giá trị cho câu hỏi số liệu |
