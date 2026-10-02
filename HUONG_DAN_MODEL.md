# Điều khiển ComfyUI cho Xưởng

Trên thanh đầu trang:

- **Bật ComfyUI · 2 GPU**: dừng đúng `vllm-qwen38.service` và
  `vllm-embed.service` bằng `systemctl --user stop`, rồi bật ComfyUI GPU0 ở
  `127.0.0.1:8188` và GPU1 ở `127.0.0.1:8189`.
- **Dừng model**: dừng hai ComfyUI, chạy lại Qwen3.8, đợi API sẵn sàng,
  rồi chạy lại Qwen3 Embedding và đợi API sẵn sàng.

Hai GPU xử lý hai cảnh song song qua hàng đợi hiện có. Đây không phải chia một
cảnh qua hai GPU. Giữ SageAttention, tắt pinned memory và dùng chế độ VRAM mặc định
khi GPU đã trống, đúng `cong_cu/comfy.sh`. Chế độ Nhanh / Chuẩn của từng dự án vẫn
hoạt động như trước. Model được nạp khi tạo cảnh đầu tiên, nên lượt đầu có thể lâu hơn.
Các cảnh vẫn mã hóa BRD sau khi tạo.

Đợi trạng thái báo sẵn sàng trước khi tạo cảnh, nhập kịch bản để AI viết prompt
hoặc tải ảnh mẫu để AI phân tích. Xem video cũ và tải ZIP không cần bật model.
Nút Dừng bị vô hiệu hóa nếu còn công việc; backend cũng kiểm tra khóa sử dụng
để tránh dừng ngang. Có thể đợi xong hoặc hủy hàng đợi bằng nút Hủy của dự án.

Quá trình đổi model chạy nền, tiếp tục khi đóng trang hoặc khởi động lại web.
Không thay các unit Qwen hay cấu hình GPU/quantization của chúng. Không dùng pkill
chung. Nếu bật ComfyUI thất bại, bộ điều khiển sẽ dừng những ComfyUI liên quan rồi
thử phục hồi cả hai Qwen, báo rõ lỗi nếu chưa phục hồi xong.

Trạng thái: `logs/model_xuong.json`. Nhật ký: `logs/model_xuong.log`, `logs/comfy.log`,
`logs/comfy_8189.log`. Lỗi Qwen xem `journalctl --user -u vllm-qwen38 -u vllm-embed`.
API quản lý `/api/xuong-model` và `/api/xuong-model/start|stop` đều yêu cầu đăng nhập.
