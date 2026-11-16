# Thuyết trình 2 phút · Bếp Trường: RAG đa phương thức cho sách nấu ăn + video

Chuẩn bị: cắm ổ T7, `docker start day6_student_starter-postgres-1`, chạy `day7-agent` → http://127.0.0.1:8780.
Để sẵn một ảnh cắt nhỏ từ video. Mở trước tab **So sánh truy xuất**: kho Kitchen KB, câu `faq32`, tick
*Hybrid · bge + full-text* và *Dense · EmbeddingGemma 2* (thêm *Hybrid + rerank* nếu còn thời gian), bấm **Chạy so sánh** một lần để
model đã nạp sẵn. Bản đầy đủ hơn (~3 phút): `report/presentation_3min.md`.

## 0:00–0:08 · Bài toán (tab Agent)
"Bếp Trường là trợ lý cho bếp ăn trường học, dựa trên sách USDA 148 trang và video hướng dẫn. Hỏi bằng chữ, ảnh hay giọng nói,
nó trả lời có nguồn tới đúng trang hoặc đúng giây."

## 0:08–0:28 · Chữ / PDF (tab PDF gốc ↔ kết quả)
"Trang được phân loại trước. Sonnet 5.5 đọc 80 trang khó như bảng và nhãn; Haiku 5.5 đọc 68 trang dễ.
Mỗi trang ra HTML giữ bảng và các fact nguyên tử. Code đối chiếu 5.443 con số với PDF, và giải mã font để chữ V bị lỗi trở lại thành ⅛.
Sau đó làm giàu thành 2.600 fact, đồ thị 551 cạnh, wiki và FAQ."

## 0:28–0:43 · Ảnh (kéo ảnh cắt vào chat)
"Mỗi ảnh (trang, 151 hình nhúng, ô cắt nhỏ) có vector CLIP và Gemma, chữ OCR và hash. Mẩu ảnh bằng 5% khung hình thì
embedding không tìm ra. So khớp điểm ảnh tìm được, rồi Sonnet tự nhìn để xác nhận: đúng giây 0:04."

## 0:43–0:58 · Video (tab Trang khó → HTML, chọn video)
"Video lấy khung mỗi giây và OCR chữ trên màn hình. Sonnet sửa '% cup' thành '⅛ cup' và gộp thành 40 đoạn có mốc thời gian,
nên 'trứng' trỏ đúng 5:40. Ảnh chụp màn hình tìm đúng mốc ±2 giây: 53/60."

## 0:58–1:13 · Âm thanh (tab Kho vector → audio_fingerprint)
"Một nút ghi âm chạy ba đường. Vân âm thanh kiểu Shazam với 114.256 hash, không cần embedding: đoạn 3 giây được nhận ra 100%.
Whisper cho giọng nói, và giai điệu cho tiếng ngân nga. Hệ thống chọn đường có bằng chứng."

## 1:13–1:35 · So sánh 2 phương pháp truy xuất (tab So sánh truy xuất, faq32)
"Cùng một câu hỏi: 'Bánh Corn and Zucchini Pancakes ăn kèm topping gì?'. Nguồn đúng là giây 7:33 của video.
Bên trái là hybrid bge cộng full-text, cách làm của Day 6. Nó trượt cả top 3, vì bắt trúng các đoạn chỉ nhắc tên món.
Bên phải là EmbeddingGemma 2: đúng 7:33 ở hạng 1, chạy cục bộ, không tốn phí. Trên 48 câu FAQ, Hit@1 là 43 so với 28.
Rerank bằng Haiku cũng sửa được câu này, nhưng chỉ vì 7:33 đã nằm sẵn trong top 20: rerank chỉ sắp lại, và tốn thêm lệnh gọi Claude."

## 1:35–1:50 · Agent (hỏi "Món nào có cá hoặc trứng?", mở phần Suy luận)
"Agent Claude Sonnet 5.5 chạy vòng ReAct, mỗi bước hiện tool, model và ảnh đang xem. Guardrail giới hạn vòng lặp và chặn lặp.
Verifier bắt kiểm chứng lại. Mỗi citation phải là bằng chứng vừa tìm."

## 1:50–2:00 · Kết luận
"Trên kho luật Day 6 cũng vậy: rerank đưa Hit@1 từ 8 lên 14, còn viết lại câu hỏi tìm thêm được bằng chứng bị sót (Hit@3 18/18).
Bài học: chọn phương pháp bằng benchmark; mỗi loại dữ liệu cần đường nạp riêng."

## Nếu bị hỏi
- **FAQ 43/48 lạc quan:** câu hỏi do LLM viết từ chính dữ liệu; con số dùng để so sánh các phương pháp với nhau.
  Trang so sánh mặc định bỏ các "gói tri thức", vì FAQ được viết từ chúng (giống benchmark).
- **Vì sao Day 6 khoá dense Gemma mà không khoá rewrite?** Trên dev, rewrite nhỉnh hơn một chút (MRR .861 so với .824), nhưng
  tốn lệnh gọi Claude và chậm hơn. Trên test, rewrite tốt hơn (MRR .806 so với .556); báo cáo ghi lại điều đó.
- **Shazam:** 100% với đoạn sạch hoặc nhiễu 10 dB; khi nhiễu to ngang tiếng gốc còn 35–38/40.
