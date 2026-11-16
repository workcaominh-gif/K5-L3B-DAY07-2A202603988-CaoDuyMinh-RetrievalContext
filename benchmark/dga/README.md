# Benchmark DGA 2020–2025 (thử thách nâng cao)

## Tài liệu nguồn
- **Dietary Guidelines for Americans, 2020–2025**, ấn bản thứ 9, USDA + HHS, tháng 12/2020.
- URL gốc: https://www.dietaryguidelines.gov/sites/default/files/2020-12/Dietary_Guidelines_for_Americans_2020-2025.pdf
- Bản local: `/Volumes/T7 Dev/AI20K/day7/dga/raw/dga_2020_2025.pdf`, **164 trang PDF**, sha256 `ceea04ce1a7c13a95a170f3548ed3926ad6dd49599bd730fb58bc9c02711d16e`.
- Quyền sử dụng: tác phẩm của chính phủ Mỹ, thuộc public domain (17 U.S.C. §105).
- Số trang in khác số trang PDF (vd. PDF p.90 = "Page 77"); mỗi evidence ghi cả `pdf_page` và `printed_page`.

## Chia split (đã chốt 2026-11-16, trước mọi thử nghiệm)

| split | table | image | chart | multihop | text | none | tổng |
|---|---:|---:|---:|---:|---:|---:|---:|
| dev  | 4 | 3 | 4 | 3 | 4 | 4 | 22 |
| test | 6 | 5 | 5 | 4 | 4 | 6 | 30 |

- Test: 24 câu có đáp án + 6 câu thiếu bằng chứng; dev: 18 + 4.
- Dev và test không trùng câu/đáp án; câu được rải khắp tài liệu (chương 1–6, phụ lục 2–3). Một số hình/bảng xuất hiện ở cả hai split nhưng hỏi **ô/panel khác nhau** (vd. Figure 1-3: test hỏi panel phụ nữ mang thai, dev hỏi panel 0–23 tháng; Table A3-2: cột/hàng khác nhau).
- Mỗi câu chỉ có **một nhóm chính** (`group`); tag phụ nằm trong `tags`.
- Sau ngày chốt, không sửa test dựa trên kết quả pipeline. Nếu buộc phải chỉnh, phải tạo test mới trước khi báo điểm.

## File
- `questions.jsonl` — 52 câu, mỗi dòng một JSON.
- `crops/<id>_<n>.jpg` — ảnh crop vùng evidence bảng/hình (PyMuPDF `get_pixmap(clip=bbox)`, 150 dpi, JPEG ~q80; tự hạ dpi nếu > 150 KB).
- `build_benchmark.py` — tái tạo `questions.jsonl` + crops từ PDF gốc (đáp án gold được viết tay trong file này).
- `../../eval/dga_verify_benchmark.py` — checker tất định.

## Ý nghĩa các trường
- `id` (`d01…`, `t01…`), `split`, `group` (`table|image|chart|multihop|text|none`), `tags`, `question` (tiếng Anh, diễn đạt khác câu gốc).
- `expected_answer`: đáp án đầy đủ, có đơn vị, điều kiện, phép tính. Với `none`: `expected_behavior: "abstain"`.
- `answerable`: bool.
- `evidence[]`: `pdf_page`, `printed_page`, `kind` (`text|table|figure`), `ref` (vd. "Table A3-2, row 'Seafood', column '2,400'"), `quote` (chuỗi con chính xác của text layer trang đó, hoặc `null`), `bbox` [x0,y0,x1,y1] theo điểm PDF (gốc trên-trái như PyMuPDF), `crop`, `reading` (với biểu đồ: cách đọc trục/chú giải/đơn vị/dung sai).
- `rationale`: câu hỏi kiểm tra năng lực gì.
- Với `none`: `absence_check` (regex đã chạy trên cả 164 trang, kết quả 0 hit theo từng pattern, regex đối chứng có hit để chứng minh phương pháp hoạt động, các trang đã xem bằng mắt) và `near_topic` (vì sao câu hỏi dễ gây "bịa").

## Cách kiểm chứng evidence với bản gốc
1. Đáp án được viết khi đọc trực tiếp ảnh render 150 dpi của trang gốc + text layer PyMuPDF; nhãn trong donut/bubble được gán theo **vị trí trong ảnh** (text layer có lúc sai thứ tự, vd. Figure 5-1).
2. Giá trị phải đọc trên trục (t16 – Figure 2-2, d11 – Figure 1-6) được đo bằng toạ độ vector (`page.get_drawings()` + vị trí nhãn tick từ `get_text("dict")`), ghi dung sai trong `reading`.
3. Mọi bảng/hình có crop để người chấm so với đáp án; các crop đã được xem lại bằng mắt.
4. `dga_verify_benchmark.py` kiểm: số câu theo split/nhóm, id duy nhất, `quote` là chuỗi con của text layer (chuẩn hoá khoảng trắng, ligature, ngoặc cong, gạch ngang), `printed_page` khớp nhãn "Page N", bbox nằm trong trang, crop tồn tại, multihop có ≥ 2 trang, chạy lại mọi regex absence → 0 hit và regex đối chứng → ≥ 1 hit, sha256 PDF.

```bash
"/Volumes/T7 Dev/AI20K/day6/venv/bin/python" -W ignore benchmark/dga/build_benchmark.py   # tái tạo (tuỳ chọn)
"/Volumes/T7 Dev/AI20K/day6/venv/bin/python" -W ignore eval/dga_verify_benchmark.py       # phải in PASS
```

## Cách ly với pipeline
Benchmark được viết độc lập từ tài liệu gốc, không đọc output của pipeline trích xuất/retrieval. **Đáp án gold, bảng gold, bbox/crop evidence chuẩn không bao giờ được đưa vào pipeline** khi index hay khi chạy; pipeline chỉ nhận `id` + `question`. Chấm điểm đối chiếu với bản gốc (crop/trang), không dựa vào nội dung model trích xuất.
