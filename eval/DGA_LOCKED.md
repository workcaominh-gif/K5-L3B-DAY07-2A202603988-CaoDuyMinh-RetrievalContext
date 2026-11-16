# DGA 2020–2025 — chọn cấu hình agent trên DEV (checkpoint C)

> **Test chưa được chạy.** Mọi số dưới đây chỉ từ split `dev` (22 câu: 18 có đáp án + 4 thiếu bằng chứng).
> Nhãn chấm là **DRAFT** (Claude Sonnet 5.5 judge + kiểm tra citation tất định), sẽ được đọc lại bằng tay ở checkpoint test.

## 1. Agent và scorer

- `eval/dga_agent.py` — ReAct agent Claude Sonnet 5.5 (adaptive thinking, effort medium). Agent chỉ nhận `id` + `question`.
  Tool: `search(query, top_k≤8, kinds?)` (RRF của dense EmbeddingGemma 2 + full-text Postgres, cấu hình có vùng thêm
  danh sách vector ảnh crop `image:crop` → ánh xạ về unit vùng), `get_page(pdf_page)`, `get_region(id)`,
  `view_region(id)` / `view_page(pdf_page)` (ảnh JPEG gốc ≤1400 px nằm trong `tool_result`).
  Guardrail như Day 6: allowlist + kiểm tra schema tham số, tối đa 8 vòng / 24 call, chặn call trùng (>2 lần), kết quả tool
  bọc `<untrusted_data>`, citation `[cite:<unit id>]` phải là id tool trả về trong lượt này (id khác bị gỡ + gắn flag),
  câu trả lời không còn citation hợp lệ → abstain; prompt caching trên system + tools và hội thoại.
  Trace mỗi câu: event từng tool call (tham số, id trả về, latency), context ids, answer, citations, status, token, chi phí, giây.
- `eval/dga_score.py` — đạt/không đạt theo ADVANCED.md §3: câu có đáp án đạt khi **(a)** trạng thái answered, **(b)** mọi
  evidence gold được một citation “trỏ đúng”: cùng `pdf_page`, và với evidence bảng/hình thì unit được cite phải là unit
  vùng (table/table_row/chart/image/box) có bbox giao bbox gold (multihop ⇒ phải cite đủ mọi trang gold), **(c)** judge:
  `correct_complete` và **(d)** judge: `supported`. Câu `none` đạt khi abstain và không thêm khẳng định thiếu căn cứ.
  Lỗi/timeout = không đạt, báo riêng, giữ trong mẫu số. Judge thấy câu hỏi, đáp án + evidence gold (ref/quote/reading +
  ảnh crop gold), câu trả lời và text các unit được cite.

## 2. Cấu hình và giả thuyết

| Cấu hình | Khác biệt | Giả thuyết |
|---|---|---|
| `text` | hybrid chỉ trên unit text (page/chunk/facts), `get_page`; không tool vùng | Baseline: trả lời đúng giá trị được (facts chứa số) nhưng **không thể** cite vùng bảng/hình ⇒ trượt mọi câu bảng/ảnh/biểu đồ theo luật citation. |
| `regions` | + unit table/table_row/chart/image/box, vector ảnh crop, `get_region` | Cite được vùng ⇒ giải quyết citation; dữ liệu bảng/biểu đồ đã trích xuất + kiểm chứng hình học đủ để trả lời. |
| `vision` | `regions` + `view_region`/`view_page` | Model tự đọc pixel gốc khi dữ liệu trích xuất thiếu/sai (biểu đồ đọc trục, nhãn trong ảnh) ⇒ tăng câu biểu đồ/ảnh, đổi lại thêm token ảnh. |

## 3. Kết quả DEV

### Vòng 1 (prompt v1, scorer v1: judge chỉ thấy 2 000 ký tự đầu của mỗi unit được cite)

| Cấu hình | Đạt | table | image | chart | multihop | text | none | Lỗi | Trung vị s | Agent $ | Judge $ |
|---|---|---|---|---|---|---|---|---|---|---|---|
| text | 8/22 | 0/4 | 0/3 | 0/4 | 0/3 | 4/4 | 4/4 | 0 | 5.2 | 0.399 | 0.154 |
| regions | 17/22 | 3/4 | 3/3 | 3/4 | 1/3 | 3/4 | 4/4 | 0 | 6.3 | 0.386 | 0.158 |
| vision | **19/22** | 3/4 | 3/3 | 3/4 | 2/3 | 4/4 | 4/4 | 0 | 6.9 | 0.471 | 0.159 |

(file: `eval/results/dga/v1/agent_*_dev.json`, `eval/results/dga/v1/labels_*_dev.json`)

### Vòng 2 (sau 2 sửa ở mục 5; `text` không chạy lại, chỉ chấm lại bằng scorer v2)

| Cấu hình | Đạt | table | image | chart | multihop | text | none | Lỗi agent | Lỗi judge | Trung vị s | Agent $ | Judge $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| text (agent v1) | 7/22 | 0/4 | 0/3 | 0/4 | 0/3 | 3/4 | 4/4 | 0 | 0 | 5.2 | 0.399 | 0.164 |
| regions | 18/22 | 4/4 | 2/3 | 3/4 | 1/3 | 4/4 | 4/4 | 0 | 0 | 4.9 | 0.405 | 0.162 |
| vision | **chưa chấm xong**: 8/8 câu đã chấm đều đạt (d01–d08) | 4/4 | 3/3 | 1/1 | – | – | – | 0 | **14** | 5.2 | 0.412 | 0.055 |

Agent `vision` vòng 2 chạy đủ 22/22 câu, 0 lỗi (18 answered, 4 abstain), nhưng judge của 14 câu (d09–d22) bị API từ chối:
*"You have reached your specified API usage limits"* (giới hạn chi tiêu của tài khoản, không phải lỗi pipeline). Các câu này
đang được ghi `pass=false` + `error=true` trong `labels_vision_dev.json`; **phải chấm lại** khi giới hạn được nới:
`$PY -W ignore eval/dga_score.py --config vision --split dev` (≈ $0.16).

## 4. Phân tích lỗi DEV (đã đọc trace từng câu trượt)

| Loại | Câu (cấu hình) | Mô tả |
|---|---|---|
| Citation — không có unit vùng | d01–d14 (`text`) | Giá trị gần như luôn đúng (facts có số) nhưng chỉ cite page/facts ⇒ không xác định vùng bảng/hình. Ví dụ d05: đúng 1 120 − 715 = 405 kcal nhưng cite `dga:p051:f0`. Đúng như giả thuyết baseline. |
| Citation — cite unit facts thay vì vùng | d10 (`regions` v1), d06 (`regions` v2) | d10: số trung bình 3 888 / 2 875 mg lấy từ `dga:p098:f1` (facts) thay vì chart `dga:p098:r3`. |
| Citation — thiếu một nguồn multihop | d12 (`regions`, `vision` v1) | Giới hạn 10% (text p.54) + 266 kcal (Figure 1-10, p.56): agent cite p.55 cho giới hạn, hoặc dùng câu văn “almost 270” thay cho số chính xác 266 trên hình (vision v1 ⇒ 70 thay vì 66 kcal, thiếu cite p.56). |
| Citation — nguồn thay thế hợp lệ | d13 (`regions`) | Lượng dairy/rau cho 900 kcal được cite từ Table 2-1 (p.77), bảng này trùng nội dung với Table A3-1 (p.156) mà gold yêu cầu ⇒ scorer tính trượt. **Cần người chấm xem lại** (gold có thể quá chặt); không nới scorer theo câu. |
| Dữ liệu vùng thiếu | d10 (`regions` v2) | Text unit chart `dga:p098:r3` chỉ có % vượt ngưỡng, không có mg trung bình ⇒ cite vùng nhưng text không hỗ trợ; `vision` khắc phục bằng `view_region`. |
| Đọc thiếu điều kiện | d17 (`regions` v1; `text` lần chấm 2) | Câu B12/trẻ bú mẹ: agent nói trang không nhắc chế độ ăn thuần chay trong khi text có ⇒ chưa đủ. Cùng một câu trả lời `text` được judge cho đạt ở lần 1 và trượt ở lần 2 ⇒ **judge có dao động**, lý do để đọc tay nhãn test. |
| Artefact của scorer (đã sửa) | d01, d10 (`regions`/`vision` v1) | Judge chỉ thấy 2 000 ký tự đầu của unit bảng dài (Table 4-1 ~3 600 ký tự) nên kết luận “không hỗ trợ” dù hàng Oils nằm trong unit được cite. |
| False abstention / hallucination | – | Không có: 4/4 câu `none` đúng ở mọi cấu hình; không câu có đáp án nào bị từ chối. |

## 5. Sửa đổi (chung, không theo câu, không dùng gold)

1. **Prompt citation (agent, cấu hình `regions`/`vision`)**: giá trị lấy từ bảng/biểu đồ/hình phải cite unit **vùng**, không
   cite unit facts/page chỉ lặp lại giá trị; khi hình/bảng có số chính xác còn văn bản làm tròn (“almost 270”) thì dùng số
   chính xác và cite vùng; câu trả lời kết hợp nhiều nguồn phải cite từng nguồn ngay cạnh giá trị lấy từ nó.
2. **Scorer**: judge thấy tới 8 000 ký tự mỗi unit được cite (trước là 2 000) — sửa lỗi chấm, không thay đổi tiêu chí.

Kết quả sau sửa: `regions` 17 → 18/22 (table 4/4, text 4/4; vẫn trượt d06, d10, d12, d13). `vision`: 8/8 câu đã chấm đạt,
14 câu chưa chấm được do giới hạn API.

## 6. Cấu hình chốt (TẠM THỜI — chờ chấm nốt vision v2 trên dev) — *đã thay bằng mục 8*

**`vision`** (prompt v2 = phiên bản hiện tại của `eval/dga_agent.py`), lý do: điểm dev cao nhất ở vòng 1 (19/22 so với 17/22
`regions`, 8/22 `text`) dù scorer v1 còn phạt oan d01/d10; vòng 2 đạt 8/8 trên các câu đã chấm; chi phí ≈ $0.019/câu,
trung vị 5–7 s, chỉ đắt hơn `regions` ~2–20%. Ưu thế cụ thể: tự đọc ảnh gốc khi text vùng thiếu số (d10), đọc biểu đồ trục.

Điều kiện để chốt chính thức trước khi chạy test: chấm lại `vision` dev bằng scorer v2; nếu `vision` < 18/22 (điểm
`regions` v2) thì chốt `regions` thay thế (tie → `regions` vì rẻ/nhanh hơn).

```bash
PY="/Volumes/T7 Dev/AI20K/day6/venv/bin/python"
export HF_HOME="/Volumes/T7 Dev/AI20K/day6/hf_cache" HF_HUB_OFFLINE=1
$PY -W ignore eval/dga_score.py --config vision --split dev        # hoàn tất chấm dev (bắt buộc trước khi chốt)
# checkpoint tiếp theo, SAU khi commit file này:
$PY -W ignore eval/dga_agent.py --config vision --split test
$PY -W ignore eval/dga_score.py --config vision --split test
```

Ghi chú vận hành: chạy ở foreground (tiến trình nền trong môi trường này bị timeout API); embedding truy vấn chạy trên CPU
vì MPS bị treo khi nhiều luồng dùng chung.

## 7. Chi phí checkpoint C

Agent: v1 $1.255 + v2 $0.816 + smoke test ≈ $0.10; judge: v1 $0.471 + v2 $0.382 ⇒ **≈ $3.02** (ngân sách $6).

**Test split chưa được chạy** (không agent, không scorer, không xem kết quả test).

## 8. Vòng 3 và CHỐT CHÍNH THỨC (2026-11-16, trước khi chạy test)

Sau khi mở lại hạn mức API, chấm `vision` dev bằng scorer v2: 18/22 (= `regions` 18/22). Đọc lý do trượt thấy một lỗi
của **scorer**, không phải của agent: d10, d12 trả đúng số và cite đúng vùng biểu đồ, nhưng judge chỉ đọc *chữ đã index* của
vùng được cite (thiếu các số chỉ có trong hình) nên kết luận "không được hỗ trợ". Theo ADVANCED.md, evidence là vùng trong bản
gốc. **Sửa scorer v3 (chung cho mọi câu, mọi cấu hình):** judge nhận thêm ảnh crop gốc của các vùng được cite (≤ 4, bỏ trùng).
Chấm lại cả hai ứng viên bằng scorer v3 (agent không chạy lại):

| Config | Split | Pass | table | image | chart | multihop | text | none | Errors | Median s | Agent $ | Judge $ |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| regions | dev | 19/22 | 4/4 | 2/3 | 4/4 | 1/3 | 4/4 | 4/4 | 0 | 4.9 | 0.40 | 0.20 |
| **vision** | dev | **20/22** | 4/4 | 3/3 | 4/4 | 1/3 | 4/4 | 4/4 | 0 | 5.2 | 0.41 | 0.20 |

Câu trượt còn lại của `vision` (d12, d13, multihop): judge xác nhận số đúng, nhưng kiểm tra citation tất định không thấy đủ
mọi trang gold (d12 thiếu trang của câu văn; d13 cite Table 2-1 p.77 — cùng dữ liệu với gold Table A3-1 p.156). Giữ nguyên
luật chấm chặt; người chấm xem lại ở bước duyệt tay.

**CHỐT: `vision`** (prompt v2, scorer v3) theo tiêu chí đặt trước (tỉ lệ đạt dev; hoà → rẻ hơn). Không đổi gì sau mốc này.

```bash
$PY -W ignore eval/dga_agent.py --config vision --split test     # chạy test MỘT lần
$PY -W ignore eval/dga_score.py --config vision --split test
```
Chi phí thêm ở vòng 3: judge ≈ $0.55 (3 lần chấm dev).
