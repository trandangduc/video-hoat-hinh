# Đăng nhập, lưu BRD và khôi phục MP4

Xưởng tại `/` yêu cầu đăng nhập cho mọi trang, API và tệp. Tài khoản quản trị
`admin` đã được tạo theo mật khẩu chủ máy cung cấp. Mật khẩu chỉ được lưu dưới dạng
scrypt trong `.bao_mat/admin.json`; cookie phiên có HttpOnly, SameSite=Strict,
Secure khi dùng HTTPS, hết hạn sau 12 giờ và bị thu hồi khi đăng xuất.
Đường dẫn chia sẻ cũ có `?ma=...` không bỏ qua đăng nhập.

## Sử dụng

- Xem cảnh và video tổng trên web như trước, có thể tua. Máy chủ giải mã từng khối
  cần phát; key không được gửi kèm luồng phát.
- **Tải ZIP mã hóa**: ZIP chứa bản tổng `bd_<mã>.brd`, không kèm file hướng dẫn.
- **ZIP gồm tất cả cảnh**: ZIP chứa bản tổng và các file `parts/*.brd`; ZIP chỉ chứa các file BRD.
- **Tool giải mã BRD**: tải công cụ riêng có giao diện chọn thư mục/ZIP, nhập key,
  chọn nơi xuất MP4. Đọc `HUONG_DAN.txt` trong tool để chạy Windows/Linux/macOS.
- **Sao lưu key**: tải `video.key` bằng phiên admin. Cất riêng khỏi ZIP và sao lưu
  ở nơi an toàn. Mất key thì không khôi phục được; tool giải mã không có key nhúng sẵn.

Key máy chủ: `.bao_mat/video.key` (32 byte ngẫu nhiên, biểu diễn Base64).
Thư mục `.bao_mat` có quyền 700, key và thông tin mật khẩu có quyền 600.
Không thay key khi còn dữ liệu cũ. Đổi key cần giải mã rồi mã hóa lại toàn bộ dữ liệu.
Có thể cấu hình `XVIDEO_KEY_FILE` để dùng vị trí key khác (cả server và worker phải dùng cùng key).
Key tách biệt hoàn toàn với mật khẩu đăng nhập.

## Định dạng và giới hạn

File đuôi `.brd` ở đây là định dạng mã hóa riêng, không phải file PCB thật.
Nội dung dùng AES-256-GCM theo khối 1 MiB; mỗi file có salt ngẫu nhiên và khóa con
HKDF-SHA256; header, vị trí và dữ liệu từng khối được xác thực. Đổi đuôi sang MP4
không giải mã được. Thiết kế dùng thư viện [cryptography](https://cryptography.io/en/latest/hazmat/primitives/aead/).

ZIP dùng chế độ lưu nguyên dữ liệu (ZIP_STORED): ciphertext không nén thêm có ích,
video gốc cũng đã nén. ZIP giúp gom tệp, không làm nhỏ video đáng kể. Muốn giảm mạnh
dung lượng cần mã hóa video ở bitrate/độ phân giải thấp hơn, có thể giảm chất lượng.

Bảo vệ này áp dụng lưu trữ của **Xưởng video tại `ra/xuong`**. Các pipeline cũ
ở `ra/du_an`, `ra/clip` nằm ngoài phạm vi chuyển đổi này, nhưng API vẫn đòi đăng nhập.
Video mới/cảnh mới chỉ được lưu lâu dài dưới đuôi `.brd`. FFmpeg và bộ tạo cảnh làm
việc trong thư mục riêng quyền 700 trên `/dev/shm`, được dọn khi thành công hoặc lỗi.
RAM tmpfs có thể được hệ điều hành đưa vào swap; SIGKILL/mất điện không chạy cleanup
Python. Đây không phải bảo đảm xóa pháp chứng hoặc DRM. Những bản MP4 cũ đã được
unlink sau khi kiểm tra SHA-256, không thực hiện ghi đè ổ đĩa. Người có quyền xem
vẫn có thể ghi màn hình hoặc lưu luồng giải mã. Phải dùng HTTPS khi truy cập từ xa.

## Kiểm tra và vận hành

Phụ thuộc bổ sung: `cryptography>=46,<48` (đã cài vào `.venv`).

```bash
.venv/bin/python -m unittest discover -s tests -v
CHIA=1 CONG=7899 .venv/bin/python giao_dien/server.py
```

Chuyển dữ liệu cũ (chỉ chạy khi đã dừng server và các worker/hàng đợi):

```bash
.venv/bin/python cong_cu/chuyen_brd.py ra/xuong
```

Công cụ chuyển đổi kiểm tra toàn bộ tag, so SHA-256 với nguồn, xuất file đích
nguyên tử rồi mới xóa MP4 cũ. Nhật ký xác minh: `logs/chuyen_brd.jsonl`.
Không tạo key mới tự động lúc khởi động, để tránh mất khả năng giải mã dữ liệu.
