# Thuyết trình ~3 phút · Bếp Trường: RAG đa phương thức cho sách nấu ăn + video

Chuẩn bị: cắm ổ T7, `docker start day6_student_starter-postgres-1`, chạy `day7-agent` → http://127.0.0.1:8780.
Để sẵn một ảnh cắt nhỏ từ video (vd thẻ tiêu đề Golden Squash Hotcakes) để kéo vào ô chat.
Bản rút gọn 2 phút: bỏ đoạn 1:30–1:55 (âm thanh) và nói gọn đoạn video.

## 0:00–0:15 · Bài toán (tab Agent)
"Bếp ăn trường học có một cuốn sách USDA 148 trang và video hướng dẫn. Câu trả lời nằm rải trong bảng nguyên liệu,
nhãn dinh dưỡng là ảnh, và chữ chỉ hiện trên màn hình video. Em xây trợ lý 'Bếp Trường': hỏi bằng chữ, ảnh hay giọng nói,
nó trả lời có nguồn tới đúng trang hoặc đúng giây trong video. Pipeline đi theo slide 7: Data, Processing, Indexing,
Enrichment, Compilation. Em đi qua từng loại dữ liệu."

## 0:15–0:45 · Pipeline chữ / PDF (tab PDF gốc ↔ kết quả)
"Bước đầu là phân loại 148 trang, không gọi model: trang bảng, trang ảnh, trang câu chuyện, trang mẹo.
Trang khó gồm 69 trang bảng, mục lục và nhãn dinh dưỡng; 5 agent Sonnet 5.5 đọc 80 trang này. 3 agent Haiku 5.5 đọc 68 trang dễ.
Mỗi trang ra hai thứ: HTML giữ nguyên bảng, và các fact nguyên tử như 'Porcupine Sliders, 50 suất: gạo lứt 9½ oz'.
Code đối chiếu 5.443 con số với text layer của PDF. Agent phát hiện font biến phân số thành chữ cái, ví dụ V là ⅛;
em giải mã quy tắc đó bằng code cho mọi trang.
Sau đó làm giàu dữ liệu: 2.600 fact, đồ thị 551 cạnh giữa công thức, nguyên liệu, dị ứng và nhiệt độ an toàn.
Biên soạn thành wiki 30 món, SOP an toàn thực phẩm và FAQ, tất cả có trích dẫn trang.
Embedding bằng EmbeddingGemma 2. Trên 48 câu FAQ, câu trả lời đúng lên hạng 1 từ 28 lên 43."

## 0:45–1:10 · Pipeline ảnh (tab Kho vector → kb_image, rồi kéo ảnh cắt vào chat)
"Ảnh được nạp ở ba mức: 148 trang, 151 hình nhúng trong PDF, và 5 ô cắt cho mỗi trang.
Ví dụ băng 'Whole Grains' là một hình duy nhất được dùng lại trên 21 trang. Mỗi ảnh có vector CLIP và EmbeddingGemma 2,
chữ OCR trong ảnh, và hash phát hiện ảnh gần trùng. Ảnh cắt chỉ bằng 5% khung hình thì embedding xếp hạng 8 đến 18.
Em thêm bước so khớp điểm ảnh ở 12 tỉ lệ. Sau đó Sonnet tự nhìn ảnh của tôi cạnh các ứng viên rồi mới trả lời,
và chọn đúng giây 0:04."

## 1:10–1:30 · Pipeline video (tab Trang khó → HTML, chọn video)
"Video tải bằng yt-dlp. Em lấy khung mỗi giây, 616 khung, vì khung đổi cảnh bỏ sót thẻ chữ hiện dần.
Apple Vision OCR đọc chữ trên màn hình. Agent Sonnet xem khung hình để sửa lỗi OCR, ví dụ '% cup' thành '⅛ cup',
rồi gộp thành 40 đoạn có mốc thời gian. Thời điểm từng nguyên liệu được OCR xác minh tới từng giây,
nên 'trứng' trỏ đúng 5:40, giây thẻ nguyên liệu hiện '3 large eggs'. Ảnh chụp màn hình tìm đúng mốc ±2 giây: 53/60."

## 1:30–1:55 · Pipeline âm thanh (tab Kho vector → audio_fingerprint, bấm phát)
"Âm thanh đi ba đường. Một: Whisper chạy local chuyển lời thành chữ, đối chiếu phụ đề YouTube để sửa tên riêng.
Video hotcakes chỉ có nhạc, Whisper trả 0 đoạn, nên chữ trên màn hình là nguồn duy nhất.
Hai: vân âm thanh kiểu Shazam, 114.256 hash cặp đỉnh phổ. Đoạn 3 giây đúng 100%, kể cả có nhiễu 10 dB.
Ba: đường giai điệu cho tiếng ngân nga. Ngoài ra mỗi cửa sổ 5 giây có vector EmbeddingGemma 2.
Chỉ một nút ghi âm: hệ thống chạy cả ba đường rồi chọn đường có bằng chứng."

## 1:55–2:30 · Agent ReAct (tab Agent, hỏi "Món nào có cá hoặc trứng?", mở phần Suy luận)
"Agent Claude Sonnet 5.5 chạy Thought, Action, Observation. Mỗi bước hiện tool, model và ảnh nó đang xem.
Câu này cần đồ thị, rồi get_recipe kiểm tra từng công thức song song. Kết quả có cả trứng trong video, đúng lúc 5:40.
Guardrail giới hạn 8 vòng và 24 lần gọi, chặn gọi lặp và trả lời lặp. Verifier bắt agent kiểm lại nếu chưa kiểm chứng.
Mỗi citation phải là bằng chứng vừa tìm thấy. Prompt cache và cache câu trả lời giúp giảm token."

## 2:30–2:50 · Kết luận
"Phần bắt buộc của lab, so 6 phương pháp trên kho luật Day 6, có trong báo cáo. Bài học chung: rerank chỉ sửa thứ hạng,
còn viết lại câu hỏi hoặc model tốt hơn mới tìm ra bằng chứng bị sót. Với đa phương thức thì mỗi loại dữ liệu cần đường
nạp riêng. Embedding chưa đủ: phải có OCR, so khớp điểm ảnh, vân âm thanh, và để model tự nhìn và tự kiểm chứng
trước khi trả lời."

## Nếu bị hỏi
- **FAQ 43/48 lạc quan:** 48 câu do LLM viết từ chính các đơn vị này. Con số dùng để so sánh các phương pháp với nhau,
  không phải độ chính xác với câu hỏi thật.
- **Shazam:** 100% với đoạn 3–10 giây sạch hoặc nhiễu 10 dB. Khi nhiễu to ngang tiếng gốc (0 dB) còn 35–38/40.
- **Ngân nga:** chỉ đáng tin với đoạn có nhạc. Đoạn chỉ có lời không có giai điệu để so.
