# Kitchen KB — từ video YouTube và sách PDF khó tới Knowledge Base cho agent

Chủ đề duy nhất: **nấu ăn lành mạnh cho trẻ ở trường / nhà trẻ (USDA Team Nutrition)**.
Thiết kế bám slide 7 bài giảng Day 7 (*Knowledge Base & RAG*): Offline **Data → Processing → Indexing → Enrichment → Compilation**,
Storage **Vector / Graph / Object Store**, Online **RAG**, Interface **API / Stream / MCP**.

## 0. Data (nguồn, đều là tác phẩm của chính phủ Mỹ → public domain, 17 U.S.C. §105)

| ID | Nguồn | Vì sao khó |
|---|---|---|
| `cookbook` | *Recipes for Healthy Kids: Cookbook for Child Care Centers*, USDA FNS 2013, govinfo GOVPUB-A98-PURL-gpo47594, 148 trang ngang, sha256 `3513…fe5d` | bảng 25/50 suất × Weight/Measure, phân số ¾ ⅛, ô trống, bước làm trải nhiều hàng; ảnh full-bleed có chữ đè; nhãn Nutrition Facts là **ảnh**; số trang in lệch PDF 2 trang |
| `yt:QhkDOr6kmi4` | CACFP Cooking Video: *Golden Squash Hotcakes* (2:23) | **không phụ đề**; chữ chỉ có trên màn hình (400 °F, 8–10 phút, ⅛ cup) |
| `yt:eSKtPtW0X2o` | *Team Nutrition Cooks! Corn and Zucchini Pancakes* (7:54) | có phụ đề → đối chiếu STT vs caption |

File thô nằm trên ổ ngoài `/Volumes/T7 Dev/AI20K/day7/raw/` (không commit).

## 1. Processing — mỗi loại nội dung một parser, chọn theo triage

`parser/triage.py` đo tín hiệu rẻ từng trang (text layer, ảnh phủ, số đường vẽ, bảng) → gán **loại trang**:
`story` · `table` · `photo` · `tips` · `toc` · `cover`. Mỗi loại đi một tuyến:

| Loại | Parser chính | Kiểm tra chéo | Đầu ra |
|---|---|---|---|
| story / tips | PyMuPDF text theo block, giữ thứ tự cột | — | Markdown theo heading |
| table | PyMuPDF `find_tables` → hàng/ô | VLM (Claude) đọc ảnh vùng bảng → so khớp từng ô; lệch → cờ `needs_review` | bảng JSON + Markdown |
| photo | text layer (chữ đè) + **VLM mô tả món** | tên món lấy từ trang lân cận (story) | caption + ảnh crop |
| ảnh nhúng (Nutrition label) | **OCR** (Apple Vision `ocrmac`, Tesseract dự phòng) | VLM đọc cùng vùng; LLM hợp nhất | bảng label |
| video | `yt-dlp` metadata + caption nếu có; không có → **STT** `faster-whisper` có timestamp | caption vs STT (WER) | transcript theo đoạn `[t0,t1]` |
| video frame | `ffmpeg` scene-change → **OCR** chữ trên màn hình → lọc trùng theo thời gian | VLM sửa phân số / chữ nghệ thuật (`% cup` → `⅛ cup`) | on-screen text `[t]` + frame |

Mọi đơn vị giữ **provenance**: `source_id`, `pdf_page`, `printed_page`, `bbox`, hoặc `t_start/t_end` + link `youtu.be/<id>?t=`,
và `extractor` (text_layer / ocr / vlm / stt / caption) + `confidence`.

## 2. Indexing

- Chunk theo **cấu trúc** (bài học Day 6: structure-aware thắng): 1 công thức = story + bảng nguyên liệu + bảng dinh dưỡng + ảnh; bảng không bị cắt giữa hàng.
- Embedding cùng model Day 6 (`BAAI/bge-small-en-v1.5`, 384) vào pgvector bảng `kb_cook`; thêm BM25 cho số liệu/tên riêng.

## 3. Enrichment (khung chấm trên slide)

| Kỹ thuật | Áp dụng cụ thể |
|---|---|
| **Metadata Enrichment** | recipe, nhóm (Whole Grains / Dark Green & Orange Veg / Dry Beans & Peas), giải thưởng, meal components, khẩu phần, nhiệt độ CCP, dị ứng (trứng, sữa, gluten, đậu nành…), modality, trang in ↔ trang PDF, timestamp |
| **Summarization** | tóm tắt 2–3 câu mỗi công thức, mỗi trang tips, mỗi video (LLM, có citation tới đơn vị gốc) |
| **Context Decomposition** | tách bảng thành **mệnh đề nguyên tử**: "Porcupine Sliders · 25 suất · gạo lứt 4 ¾ oz (¾ cup)"; tách Directions thành bước; tách nhãn Nutrition thành từng dòng |
| **Graph Extraction** | `Recipe —has_ingredient(qty,servings)→ Ingredient`, `Recipe —in_category→ Category`, `Recipe —has_ccp→ Temp`, `Ingredient —allergen→ Allergen`, `Video —demonstrates(t)→ Step/Recipe` |

## 4. Compilation — Knowledge packages

- **Wiki**: 1 trang Markdown / công thức (cookbook + video nếu có), mọi câu có citation.
- **SOP**: *An toàn thực phẩm khi nấu cho trẻ* — gom mọi Critical Control Point, rửa tay 20 giây (video), nhiệt độ nấu/làm nguội.
- **FAQ**: Q&A sinh từ đơn vị đã phân rã, mỗi câu trỏ về trang/bbox/timestamp; người kiểm duyệt trước khi dùng.
- **Glossary**: CCP, CACFP, meal components, oz eq…

## 5. Storage

Vector Store = pgvector (`kb_cook`), Graph Store = bảng `kg_edges` (Postgres, có thể xuất JSON),
Object Store = thư mục `objects/` trên T7 (crop bảng, ảnh, frame) định danh bằng URI `obj://cookbook/p12/table1.png`.

## 6. Online & Interface

Agent RAG (Day 7) dùng tool `search` (dense / BM25 / hybrid), `graph_lookup`, `open_object`; trả lời có citation trang/timestamp.
Interface: HTTP API, stream (SSE) câu trả lời, và MCP server (resources `recipe://…`, tools `search`).

## Kiểm chứng

Mỗi bước có số liệu: % trang theo tuyến, ô bảng khớp OCR↔VLM, WER STT vs caption, số mệnh đề / cạnh graph,
và benchmark câu hỏi (bảng, ảnh, video, multi-hop, thiếu evidence) chấm tay theo ADVANCED.md.
