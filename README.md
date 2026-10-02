> **Điều khiển GPU:** nút Bật ComfyUI · 2 GPU / Dừng model tự chuyển giữa ComfyUI và hai Qwen. Xem [hướng dẫn model](HUONG_DAN_MODEL.md).

> **Cập nhật 16/09/2026:** Xưởng yêu cầu đăng nhập; toàn bộ video trong `ra/xuong` được mã hóa đuôi `.brd`, tải ZIP và có tool giải mã bằng key. Xem [hướng dẫn bảo mật](HUONG_DAN_BAO_MAT.md). Các hướng dẫn `?ma=` bên dưới là cơ chế cũ.

# Video hoạt hình từ kịch bản + ảnh cảnh

> **Cài trên máy mới** (clone ở thư mục nào cũng được, script tự tìm gốc repo):
>
> ```bash
> bash cong_cu/cai_dat.sh                      # venv + torch cu128 + chatterbox + web + ffmpeg + ComfyUI
> .venv/bin/python cong_cu/tao_admin.py        # tạo tài khoản admin + .bao_mat/video.key (giữ key cũ nếu có)
> .venv/bin/python -m unittest discover -s tests
> .venv/bin/python giao_dien/server.py
> ```
>
> Chuyển từ máy cũ sang thì chép `.bao_mat/video.key` sang **trước** khi chạy `tao_admin.py`,
> không thì video `.brd` cũ không giải mã được. Model (`models/`) tải bằng `cong_cu/tai_*.sh`.

Làm video hoạt hình có thoại, **chạy hoàn toàn trên máy này**, không gửi gì ra mạng.

Ba bước, theo đúng thứ tự này và **không được đảo**:

| | bước | model | ra cái gì |
|---|---|---|---|
| 1 | Tiếng | Chatterbox (Resemble AI) | `ra/tieng/<cảnh>.wav` |
| 2 | Hình | Wan 2.2 S2V-14B (cảnh có thoại) · Wan 2.2 I2V-A14B (cảnh không thoại) | `ra/clip/<cảnh>.mp4` |
| 3 | Ghép | ffmpeg | `ra/video_cuoi.mp4` |

Vì sao không đảo được: Wan S2V **nhận audio làm đầu vào** và sinh clip khớp miệng theo
audio đó, nên **độ dài tiếng quyết định độ dài clip**. Làm hình trước rồi mới làm tiếng là
phải cắt/kéo cho khớp, hỏng cả nhịp.

---

## Tôi bỏ file vào đâu

```
vao/
├── kich_ban.json      danh sách cảnh (có sẵn file mẫu 3 cảnh)
├── canh/              canh_01.png, canh_02.png, ...  (ảnh đã có sẵn nhân vật)
└── giong_mau.wav      tuỳ chọn: 5-10 giây giọng mẫu để nhân bản
```

Ảnh nên đúng **832×480** (hoặc tỉ lệ đó); kích thước phải chia hết cho 16.

### `kich_ban.json`

```json
{
  "ten_video": "Tên gì cũng được",
  "cau_hinh": { "fps": 16, "rong": 832, "cao": 480,
                "giay_canh_khong_thoai": 5, "phu_de": true },
  "canh": [
    { "id": "canh_01",
      "anh": "canh_01.png",
      "thoai": "Câu thoại tiếng Anh. Để trống nghĩa là cảnh không thoại.",
      "cam_xuc": "hoi_hop",
      "ghi_chu": "Mô tả chuyển động — cái này thành prompt cho Wan." }
  ]
}
```

`cam_xuc` chọn một trong: `binh_thuong` · `vui` · `buon` · `nhe_nhang` · `hoi_hop` ·
`cang_thang` · `gian` · `trang_trong`. Nó chỉnh hai tham số của Chatterbox
(`exaggeration` và `cfg_weight`) — xem bảng trong `scripts/chung.py`.

---

## Gõ lệnh gì

## Xưởng video — tự viết từng cảnh rồi merge (trang chính)

```bash
.venv/bin/python giao_dien/server.py            # chỉ máy này
CHIA=1 .venv/bin/python giao_dien/server.py     # cho người khác trong mạng LAN
```

Mở địa chỉ nó in ra. Trình tự:

1. **+ Dự án mới**, đặt tên.
2. **Cài đặt chung**: phong cách (tự gõ tiếng Anh, hoặc bấm mẫu), ảnh mẫu (tuỳ chọn — máy tự đọc
   ảnh thành một câu tả nhân vật, sửa được), giọng đọc (giọng mặc định hoặc tải 5–10 giây giọng
   mẫu để nhân bản, chọn cảm xúc), nhạc nền (tuỳ chọn), hiệu ứng phim cũ.
3. **Mỗi cảnh**: viết **prompt hình** (tiếng Anh), **lời đọc** (tiếng Anh, để trống nếu không
   có lời), chọn cách dùng ảnh mẫu (không dùng · tả nhân vật vào prompt · ảnh làm khung mở đầu).
   Cảnh **có lời** tự dài bằng giọng đọc + 0,5 giây; cảnh **không lời** kéo thanh chọn số giây.
4. Bấm **Tạo cảnh** từng cái (hoặc **Tạo tất cả cảnh chưa có**), xem thử ngay trong thẻ cảnh.
   Chưa ưng thì sửa rồi **Tạo lại** — chỉ cảnh đó vẽ lại, cảnh khác giữ nguyên.
5. Ưng hết thì **Merge video** → xem → **Tải video về**. Sửa cảnh sau khi merge thì video tự hiện
   nhãn *cũ*; merge lại chỉ mất vài giây.

**Tối đa bao nhiêu giây một cảnh** — đo ngày 10/09/2026 trên RTX 5090, GPU0 trống, 1280×704,
LTX-2.5 dev, 30 bước (số đo nằm ở `logs/xuong_cau_hinh.json`, thanh chọn giây đọc từ đó):

| cảnh | VRAM đỉnh | vẽ mất khoảng |
|---|---|---|
| không ảnh mẫu, 10 giây | 27,3 GB | 10,5 phút |
| không ảnh mẫu, 15 giây | 26,6 GB | 15 phút |
| không ảnh mẫu, **20 giây** | **30,2 GB** / 32,6 | 21 phút |
| ảnh làm khung mở đầu, 10 giây | 28,5 GB | 14 phút |
| ảnh làm khung mở đầu, 15 giây | 28,7 GB | 22 phút |
| ảnh làm khung mở đầu, **20 giây** | 27,5 GB | 32 phút |

Giới hạn là **20 giây**. Cái tăng theo độ dài là **thời gian**, không phải VRAM (ComfyUI tự điều
phối bộ nhớ — cảnh 15 giây còn dùng ít VRAM hơn cảnh 10 giây). Nhưng cảnh 20 giây không ảnh mẫu đã
chạm 30,2 GB: GPU0 mà có tiến trình khác (vLLM…) chiếm chỗ thì cảnh 20 giây sẽ tràn. Đo đỉnh VRAM
chỉ cần 2 bước lấy mẫu vì đỉnh không phụ thuộc số bước — mỗi mức đo mất 1–4 phút thay vì 10–30.

**Tốc độ vẽ — Chuẩn hay Nhanh** (nút trong Cài đặt chung, áp cho cả dự án). Đo ngày 11/09/2026 trên
cùng một cảnh collage 5 giây (121 khung, 1280×704), cùng seed, RTX 5090 — `cong_cu/do_toc_do.py`; so
hình bằng `cong_cu/luoi_so.py` (`ra/do_toc_do/luoi.png`, `luoi_cat.png` là ô cắt 100%):

| cách vẽ | thời gian | nhanh hơn | hình ở 100% |
|---|---|---|---|
| **Chuẩn** — dev int8, 30 bước, CFG 3/7 | 272 s | — | sạch, ít chi tiết |
| dev 20 bước | 192 s | 1,42× | lấm tấm nhiễu trên quần áo, tuyết |
| dev + EasyCache / LazyCache (ngưỡng 0,2) | 272 / 276 s | 1,00× | EasyCache bỏ 0/30 bước; LazyCache báo bỏ 9/30 mà giờ vẽ không giảm |
| dev 2 tầng (640×352 → phóng latent ×2 → 3 bước) | 114 s | 2,38× | **vân lưới** trên áo, balo; đổi sampler `euler` hay 8 bước tầng 2 vẫn còn |
| distilled 1 tầng, 8 bước | 74 s | 3,68× | sạch, nhưng người gần như đứng im |
| **Nhanh** — distilled 2 tầng (8 bước 640×352 → ×2 → 3 bước) | **58 s** | **4,69×** | **nét nhất**: mặt, dây balo, nếp áo rõ; có chuyển động |

Nhanh là đúng pipeline chính thức của Lightricks (`workflows/goc_ltx/LTX-2.5_T2V_I2V_Two_Stage_Distilled.json`);
cảnh dùng ảnh làm khung mở đầu được gắn lại ảnh ở tầng 2 như bản chính thức. Cái giá: model distilled
chạy cfg 1 nên **prompt âm không có tác dụng** — thỉnh thoảng hiện chữ lạ trên giấy trong cảnh collage.
Cách dùng hợp lý: **nháp bằng Nhanh**, duyệt, rồi chuyển **Chuẩn** và bấm **Tạo** — nút tạo hết sẽ vẽ lại
đúng những cảnh đang là bản nhanh. Đổi chế độ không làm hỏng gì: cảnh đã vẽ vẫn "xong", vẫn merge được,
thẻ cảnh chỉ gắn nhãn *bản nhanh*.

**Một cảnh 10 giây mất bao lâu** (249 khung, RTX 5090, model đã nạp sẵn; `cong_cu/do_10s.py`,
`logs/do_10s.jsonl`):

| cách vẽ cảnh | 10 giây | ra |
|---|---|---|
| Nhanh | **~2 phút** (118 s) | 1280×704 |
| Nhanh + ảnh làm khung mở đầu | **~3 phút** (178 s) | 1280×704 |
| Giữ nhân vật (bảng tham chiếu) | **~5 phút** (298 s) | 1536×896 |
| Chuẩn | **~11 phút** | 1280×704 |
| Chuẩn + ảnh làm khung mở đầu | **~15 phút** | 1280×704 |

Cộng thêm nếu có: cảnh **đầu tiên sau khi đổi** kiểu vẽ (Chuẩn ↔ Nhanh/Giữ nhân vật) +1–1,5 phút nạp
model; **lời đọc** +10–15 giây mỗi cảnh; **merge** cả video ~15 giây. Số Chuẩn lấy từ lần đo 10/09 ở
241 khung (10,5 và 14,3 phút). Ví dụ video 1 phút = 6 cảnh 10 giây: Nhanh ~13 phút, Giữ nhân vật
~31 phút, Chuẩn ~66 phút.

**Đổi model không tràn RAM.** ComfyUI nạp model mới mà vẫn giữ model cũ trong RAM (dev 21,5 GB +
distilled 18,7 GB + Gemma 15 GB > 60 GB). `du_an.chay_wf` nhớ model của lần vẽ trước
(`logs/comfy_unet.txt`); khác thì gọi `/free` của ComfyUI và chờ nhả xong mới gửi — đo được RSS của
ComfyUI 41,1 GB → 4,5 GB sau ~10 giây. Lần vẽ đầu sau khi đổi chế độ mất thêm thời gian nạp model.

**Kiểm thử đầu–cuối** — `cong_cu/thu_xuong_dau_cuoi.py` bấm qua API y như trên web (tạo dự án, tải ảnh
mẫu, viết cảnh, Tạo hết, Merge, đổi chế độ), ghi từng bước vào `logs/thu_xuong_dau_cuoi.json`. Lần chạy
11/09/2026 ở chế độ Nhanh: cảnh t2v 5 giây vẽ 135 s (gồm nạp model), cảnh có lời đọc 5,58 giây
(137 khung) 67,7 s, cảnh ảnh làm khung mở đầu 4 giây (105 khung) 73,2 s; cả dự án từ lúc bấm Tạo hết
tới xong 290 s, merge ra video 14,6 giây. Chuyển sang Chuẩn: 3 cảnh vẫn "xong", video vẫn "mới nhất".
Vẽ lại cảnh 1 ở Chuẩn: 368,6 s (≈ 290 s vẽ + ~80 s xả distilled rồi nạp lại dev và Gemma), RAM không
tràn; đổi ngược về Nhanh: 134 s (≈ 68 s vẽ + ~65 s nạp). Lần kiểm thử này bắt được một lỗi đã sửa: vẽ lại cảnh ở chế độ khác mà video đã merge vẫn báo
"mới nhất" — dấu của bản ghép giờ tính cả chế độ vẽ của từng clip. Chạy lại toàn bộ sau khi sửa: qua
hết (vẽ lại xong video báo "cũ"), RAM trống thấp nhất 10,4 GB.

**Nhân vật có giống nhau giữa các cảnh không** — tuỳ cách dùng ảnh mẫu, thấy rõ trong lần kiểm thử trên:

- **Ảnh làm khung mở đầu**: giống nhất. Clip bắt đầu đúng bằng ảnh rồi mới cử động, nên nhân vật, nét vẽ,
  quần áo giữ nguyên (thử với nhân vật nón lá: nón, áo hoa, nét 2D viền đen đều giữ). Đổi lại cảnh nào
  cũng mở đầu bằng cùng một khung hình; ảnh không phải 16:9 thì hai bên được đệm bằng chính ảnh làm mờ.
- **Tả nhân vật vào prompt**: chỉ giống **bằng chữ**, cảnh tự do hơn nhưng dễ trôi. Câu tả tự sinh kiểu
  cũ ("cartoon-style … straw hat") làm LTX vẽ ra nhân vật **3D** đội **mũ rơm vành tròn** trong khi ảnh
  là 2D đội nón lá. Máy đọc ảnh giờ bắt đầu câu tả bằng **nét vẽ** và gọi tên đồ vật chính xác
  ("Flat 2D cartoon with thick black outlines … conical straw hat …"). Vẽ lại cùng cảnh với câu tả mới
  (chế độ Nhanh, 69,6 s): ra đúng nét 2D có viền, đúng nón lá, áo hoa hồng, mặt cau có — nhưng người
  thành **béo tròn** vì máy tả nhầm "round body" (ảnh là đầu to, thân nhỏ). Nên **đọc lại câu tả và sửa
  chỗ sai** (ví dụ "big round head, small slim body") trước khi tạo cảnh; muốn giống hệt thì dùng ảnh
  làm khung mở đầu.
- **Không dùng**: mỗi cảnh một nhân vật khác.
- **Giữ nhân vật (bảng tham chiếu)** — cách tốt nhất: cảnh tự do mà nhân vật vẫn là **một người**. Dùng
  IC-LoRA Ingredients của Lightricks (`models/loras/ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors`).
  Tải ảnh mẫu là máy tự tách nền (BiRefNet, `cong_cu/tach_nen.py`) và dựng **bảng tham chiếu** hiện ngay
  trong ô Ảnh mẫu; cảnh nào chọn *Giữ nhân vật* thì vẽ theo bảng. Luôn vẽ bằng model distilled 2 tầng,
  không theo nút Chuẩn/Nhanh: ~146 s cho cảnh 5 giây, ~298 s cho cảnh 10 giây (nhân vật vẫn giữ tới
  cuối), ra 1536×896, tối đa 10 giây. Bảng được lặp **đúng bằng số khung của cảnh** — lặp ≥ 121 khung
  như model card ghi thì cảnh ngắn (lời đọc 2,5 giây → 81 khung) báo lỗi "Conditioning frames exceed
  the length of the latent sequence" (kiểm thử đầu–cuối bắt được, đã sửa).

**Giữ nhân vật — đã thử những gì** (`cong_cu/thu_ingredients.py`, lưới so ở `ra/thu_ingredients/`), cùng
3 cảnh (đi trong tuyết · ngồi viết · chỉ bản đồ):

| cách | kết quả |
|---|---|
| Không LoRA, tả nhân vật bằng chữ | cảnh đẹp nhưng **3 người khác nhau** (hói · cậu bé · ông béo) |
| LoRA, bảng 2 hình trên nền đen, prompt tả chung, 960×544 | video **chép nguyên bảng** (nhân vật đứng yên trên nền đen) |
| LoRA, bảng đúng mẫu, vẽ 640×352 rồi phóng | có cảnh chép bảng, có cảnh ra **2 người** (dáng lật gương thành người thứ hai) |
| **LoRA, bảng đúng mẫu, vẽ 768×448** (dev hoặc distilled) | **3/3 cảnh đúng một nhân vật**, giống bảng; distilled cử động tốt hơn, 95 s |
| + tầng 2 phóng lên 1536×896 từ sigma 0,85 | vẽ lại chi tiết → **mất mặt**, quần áo thành kiểu ảnh thật |
| **+ tầng 2 từ sigma 0,42** (đang dùng) | nhận dạng y hệt, **nét hơn rõ** (viền, hoa văn áo, vân nón), 146 s |

Ba điều bắt buộc, học được qua các lần hỏng trên (khớp với model card và video mẫu của Lightricks):
1. **Bảng đúng kiểu**: phủ kín khung, mỗi yếu tố một ô **nền xám nhạt**, khe đen, không chữ — ô cận mặt +
   ô toàn thân. Bảng lặp thành video tĩnh ≥ 121 khung.
2. **Vẽ đúng 768×448** (kích thước LoRA được huấn luyện). Lệch đi là model coi bảng là khung hình.
3. **Prompt hai phần**: `Reference sheet: <tả TỪNG Ô>` rồi `Generated video: <cảnh>` — máy tự ghép từ câu
   tả ảnh mẫu và prompt của cảnh.

Còn hạn chế: nền thường ra kiểu ảnh thật dù nhân vật là hoạt hình, đôi khi mờ sương; nhân vật hay mượn
dáng đứng trong bảng (tay chỉ ngang); chỉ có một ảnh nhìn thẳng nên "nhiều góc" chỉ là dáng lật gương.
ComfyUI ở đây không có node riêng của ComfyUI-LTXVideo nên dùng node gốc tương đương:
`LoraLoaderModelOnly` + `GetICLoRAParameters` + `LTXVAddGuide` + `LTXVCropGuides`.

**Chạy nền.** Mọi nút Tạo và Merge chỉ **xếp việc vào hàng đợi** (`ra/xuong/hang_doi.json`). Mỗi GPU
có một tiến trình `cong_cu/hang_doi.py gpu0|gpu1` tự lấy việc tới hết rồi thoát, nên đóng trình duyệt
hay tắt server vẫn chạy xong. Server có "lính gác" cứ 4 giây kiểm tra: có việc mà GPU nào đang nghỉ thì
bật tiến trình cho GPU đó, kể cả sau khi server khởi động lại.

**Vẽ song song trên 2 GPU** (từ 11/09/2026). Hai ComfyUI: GPU0 ở :8188, GPU1 ở :8189 — mỗi GPU vẽ một
cảnh cùng lúc (một lượt vẽ chiếm 20–30 GB nên một card 32 GB không chứa được hai). Đo được:
- 4 cảnh Nhanh 5 giây xong trong **180 s thực** so với tổng 354 s vẽ — **nhanh 1,97×**
  (`cong_cu/thu_song_song.py`, `logs/thu_song_song.json`).
- Trước đây không chạy nổi hai ComfyUI vì mỗi bản giữ **40 GB RAM** (bộ nhớ ghim — pinned memory — mặc
  định của ComfyUI). `cong_cu/comfy.sh` giờ bật với `--disable-pinned-memory`: **~5 GB RAM mỗi bản**,
  tốc độ vẽ không đổi (57,1 s so với 58,0 s cùng cảnh). Hai GPU cùng vẽ, RAM còn trống thấp nhất 41,7 GB.
- Mỗi tiến trình đọc giọng (Chatterbox ~3,2 GB) trên chính GPU của nó.

Luật lấy việc: GPU rảnh lấy cảnh kế tiếp — hai cảnh **cùng dự án** vẽ song song được. Có nhiều dự án
thì ưu tiên dự án **đang không có cảnh nào vẽ và chờ lâu nhất**, nên dự án 50 cảnh không chặn dự án
khác. Merge một dự án chờ tới khi dự án đó hết cảnh đang vẽ. Nút Huỷ dừng đúng GPU đang vẽ việc của dự án.

```bash
bash cong_cu/comfy.sh len                                         # GPU0 :8188
CUDA_VISIBLE_DEVICES=1 COMFY_PORT=8189 bash cong_cu/comfy.sh len   # GPU1 :8189
XUONG_MAY=gpu0 CHIA=1 CONG=7899 .venv/bin/python giao_dien/server.py   # chỉ dùng GPU0 (vd GPU1 cho vLLM)
```

**Theo dõi tiến độ.** Thanh chung dưới tên dự án (xanh = cảnh xong, cam = phần đang vẽ dở, kèm thời gian còn
lại theo số GPU); thanh chạy có một dòng cho mỗi GPU; khung xem của cảnh đang vẽ có thanh % đè lên; danh
sách dự án bên trái có thanh nhỏ. Phần trăm là số THẬT: `du_an._TheoTienDo` đọc thanh tqdm ComfyUI in vào
log của chính ComfyUI đang vẽ (`logs/comfy.log` / `logs/comfy_8189.log`) — pha nạp model → vẽ tầng 1/2,
bước k/n (giây còn lại theo tốc độ s/bước) → giải mã → đóng gói; dòng có tổng bước không khớp workflow (vd
Gemma đang viết prompt cùng ComfyUI) bị bỏ qua. Mỗi cảnh ghi tiến độ riêng `ra/xuong/<mã>/tien_do/<cảnh>.json`
vì hai GPU vẽ song song hai cảnh cùng dự án. Ô **Tìm dự án** lọc theo từng từ, không cần dấu.

Chỉ còn giao diện Xưởng video: `/ke-chuyen` và `/nang-cao` chuyển về trang chính (mã cũ vẫn giữ trên đĩa).

**Truy cập từ xa — URL cố định** `https://rndcentral.tail94785a.ts.net/?ma=<mã>` (mã ở `logs/ma_chia.txt`;
không mã → 403). Chạy bằng **Tailscale Funnel** trên instance Tailscale riêng của chủ máy (`ts2`, userspace,
socket `/tmp/ts2/tailscaled.sock`, tự bật qua `ts2.service` / cron @reboot / `~/start_ts2.sh`) — không đụng
Tailscale root của tailnet khác trên máy. Bật lại khi cần:
```bash
tailscale --socket=/tmp/ts2/tailscaled.sock funnel --bg 7899      # tắt: ... funnel reset
CHIA=1 MA="$(cat logs/ma_chia.txt)" CONG=7899 .venv/bin/python giao_dien/server.py
```
Hai lỗi đã gặp: `ts2` thiếu `--statedir` nên không xin được chứng chỉ HTTPS ("no TailscaleVarRoot") — đã
thêm vào cả 3 chỗ khởi động; và sau khi có chứng chỉ phải `funnel reset` rồi bật lại thì Tailscale mới công
bố DNS công cộng. DNS mới có thể mất vài chục phút mới tới mọi nơi (Google 8.8.8.8 thấy trước Cloudflare 1.1.1.1).
Link tạm trycloudflare đã bỏ.

**Nhập kịch bản** (nút *⇪ Nhập kịch bản*): tệp `.docx` / `.txt` / `.md` hoặc dán chữ. Có mốc giờ kiểu
`[00:00 – 00:07] Segment 1 …` thì mỗi mốc một cảnh (chữ dính liền "Segment 1On the night…" vẫn tách
đúng); không có mốc thì mỗi đoạn văn một cảnh. Dòng VIẾT HOA là tên mục (INTRO, THE EXPEDITION…) hiện trên
thẻ cảnh; dòng đầu thành tên dự án. Đoạn dài quá giới hạn của cách dùng ảnh đã chọn thì tách theo câu.
Thử với kịch bản Dyatlov 57 đoạn: 57 cảnh, ~590 giây; chọn *Giữ nhân vật* (10 giây/cảnh) thì 71 cảnh.
`cong_cu/nhap_kich_ban.py` tách được cả khi chạy tay.

**Không cần viết prompt hình.** Ô *Prompt hình* để trống thì máy (Gemma E2B, trên ComfyUI nào đang rảnh
hơn) tự viết từ lời đọc của cảnh, có tham khảo lời cảnh trước/sau, theo công thức collage nếu dự án dùng
phong cách collage — ~3 giây mỗi cảnh, thẻ cảnh ghi *máy viết từ lời đọc, sửa được*. Bấm Tạo khi prompt
còn trống thì máy viết xong mới tự xếp vẽ. Đừng dán câu **phong cách** vào ô prompt hình ("vintage sepia
collage, film grain, rapid montage…"): LTX sẽ vẽ nền giấy mờ không có chủ thể — phong cách đã có ô riêng.

**Không vẽ lại vô ích.** Mỗi cảnh có mã riêng (đổi thứ tự không mất bản đã vẽ) và dấu vân tay của
prompt đầy đủ + số khung + ảnh mẫu + seed; lời đọc có dấu vân tay riêng. Bấm Tạo mà không đổi gì thì
giữ bản cũ ngay; chỉ sửa lời đọc mà độ dài không đổi số khung thì hình vẫn giữ.

**File.** `ra/xuong/<mã>/`: `du_an.json`, `tieng/<cảnh>.wav`, `clip/<cảnh>.mp4`, `video.mp4`. Chạy
tay không cần web: `CUDA_VISIBLE_DEVICES=1 .venv/bin/python cong_cu/xuong.py canh ra/xuong/<mã>/du_an.json <cảnh>`
và `... xuong.py merge ra/xuong/<mã>/du_an.json`.

**Giới hạn**
- Giọng đọc **chỉ tiếng Anh**: Chatterbox trên máy có 23 ngôn ngữ nhưng không có tiếng Việt.
- Chatterbox **không chỉnh được tốc độ đọc**, vì vậy cảnh bám theo độ dài giọng chứ không ép giọng.
- Lời đọc dài hơn 19,5 giây (tối đa 20 giây trừ 0,5 giây đuôi) thì cảnh báo lỗi, phải tách cảnh.

## Tạo video bằng cách kể chuyện (trang /ke-chuyen)

```bash
.venv/bin/python giao_dien/server.py            # chỉ máy này
CHIA=1 .venv/bin/python giao_dien/server.py     # cho người khác trong mạng LAN
```

Mở địa chỉ nó in ra. Trang chính giờ là **Xưởng video**: gõ câu chuyện bằng lời thường (tiếng
Việt được), bấm **Lên kịch bản**, xem lại các cảnh, sửa nếu muốn, bấm **Tạo video**. Quy
trình từng bước cũ vẫn còn ở `/nang-cao`.

| bước | ai làm | mất bao lâu |
|---|---|---|
| Đọc ảnh mẫu (nếu có) | Gemma-4 E2B, tại máy | ~3–15 giây |
| Chia cảnh, viết prompt, chọn chữ chèn | Gemma-4 E2B, tại máy | ~20–30 giây |
| Bạn sửa bảng cảnh | bạn | tuỳ |
| Vẽ từng cảnh | LTX-2.5 dev | ~1,5 phút mỗi cảnh ngắn |
| Vẽ chữ, **tự tìm chỗ trống đặt chữ**, cắt viền, ghép | ffmpeg + PIL | vài giây mỗi cảnh |

**Tuỳ chọn khi kể chuyện**
- **Độ dài** 10–60 giây và **nhịp** (cắt nhanh 0,6–1,8 giây/cảnh · vừa 2–4 · chậm 4–7).
- **Phong cách**: 7 mẫu dựng sẵn, hoặc để máy tự chọn theo câu chuyện.
- **Ảnh mẫu**: máy đọc ảnh và tả nhân vật thành một câu, rồi ghép câu đó vào mọi cảnh có nhân
  vật. Bật thêm **Bám sát ảnh mẫu** thì các cảnh có nhân vật dùng chính ảnh làm khung mở đầu
  (i2v) — giống hơn, nhưng các cảnh đó mở đầu y hệt nhau.
- **Nhạc**: có thì dùng làm tiếng nền; không có thì tổng hợp tiếng gió.

**Chạy nền.** Bấm Tạo video xong đóng trang được. Mở lại là thấy tiến độ theo từng cảnh. Máy
tắt giữa chừng thì dự án hiện *Dừng giữa chừng*; bấm Tạo video lần nữa là chạy tiếp — cảnh
nào đã vẽ mà prompt không đổi thì được giữ, chỉ vẽ cảnh mới hoặc cảnh đã sửa.

**File nằm ở đâu.** Mỗi dự án một thư mục `ra/du_an/<mã>/`: `du_an.json` (kịch bản),
`clip/cNN.mp4` (từng cảnh), `chu/` (ảnh chữ), `video.mp4` (kết quả). Chạy tay không cần web:
`.venv/bin/python cong_cu/du_an.py ra/du_an/<mã>/du_an.json`.

**Giới hạn cần biết**
- **Gemma-4 12B (encoder của LTX) không sinh chữ được** — thử ra toàn `SSSS…` — nên bước lên
  kịch bản dùng bản **E2B** nhỏ. Nó hay phạm luật (tổng giây lệch, chữ chèn sai ngôn ngữ,
  prompt trừu tượng, tự thêm `film grain`, cảnh nào cũng chèn chữ), nên `cong_cu/len_kich_ban.py`
  sửa lại sau khi đọc JSON. Kịch bản vẫn có thể nhạt — vì vậy mới có bước bạn xem và sửa.
- Model chạy greedy nên hỏi lại y nguyên sẽ ra y nguyên; nút **Lên lại** thêm một dòng nhắc
  "phương án khác" để đổi câu trả lời.
- **"Tự chọn phong cách" không có nghĩa để model tự bịa.** Đo được: Gemma tự đặt phong cách
  *"Dark, dramatic, historical"* rồi viết prompt nào cũng *dim / dark / shadows* — video Marie
  Curie ra tối đen, độ sáng trung bình 9–12 trên 255, cảnh 3 gần như màn hình đen. Nên model chỉ
  được **chọn một trong 6 mẫu** (`PHONG_CACH_MAU` trong `len_kich_ban.py`, giao diện đọc cùng danh
  sách qua `/api/phong-cach`), phải viết cảnh đủ sáng, và prompt nào còn chữ tối thì tự được nối
  *"clearly lit and visible"*.
- **Cảnh tối không bị cắt viền.** Ở cảnh tối, viền và nội dung tối không tách được (đo: 230–460
  hàng tối liên tiếp mà đều là nội dung; một cảnh bị cắt nhầm, zoom 1,43×). Khung có độ sáng trung
  bình dưới 45 bị bỏ qua khi dò viền — không cắt còn hơn cắt sai.
- **LTX đôi khi bỏ qua vật thể trong prompt.** Bấm "đã render" ở từng cảnh để xem nhanh.
- **Font chữ chèn:** Caveat, Kalam, Special Elite, Courier Prime **thiếu dấu tiếng Việt** (thiếu
  34–56 ký tự như ơ ư ạ ấ ệ, đo bằng fontTools). Mỗi dòng chữ tự chọn font đầu tiên phủ đủ ký
  tự của nó theo bảng `cong_cu/phong/bang_chu.json`: chữ viết tay → Caveat, rồi Patrick Hand;
  chữ máy đánh → Special Elite, rồi IBM Plex Mono; cuối cùng là DejaVu.

### Cách dễ nhất — giao diện web

```bash
.venv/bin/python giao_dien/server.py
```

Nó tự dò cổng trống (máy này đang có app khác giữ 7860/7870) và in địa chỉ ra màn hình,
thường là <http://127.0.0.1:7880>. Trong đó kéo thả ảnh vào, sửa lời thoại, bấm chạy,
xem nhật ký và xem video — không cần nhớ lệnh nào.

**Việc chạy nền.** Bấm chạy xong là đóng trình duyệt được, tắt luôn cả server cũng được
— việc vẫn chạy tiếp. Mở lại trang là thấy đúng tiến độ và toàn bộ nhật ký từ đầu, rồi
bấm **Tải về** lấy video. (Máy tính thì vẫn phải để bật: việc chạy trên GPU của máy này,
tắt nguồn là mất.) Làm được vậy vì tiến trình chạy ở phiên riêng
(`start_new_session`), log ghi thẳng ra `logs/viec/*.log` và trạng thái nằm ở
`logs/viec/hien_tai.json` chứ không giữ trong bộ nhớ server. Xem `giao_dien/viec.py`.

**Chia cho người khác.**

```bash
CHIA=1 .venv/bin/python giao_dien/server.py
```

Nó in ra một địa chỉ kèm mã, kiểu `http://192.168.2.230:7880/?ma=AQoJcyei_PQh`. Gửi
nguyên địa chỉ đó cho người cùng mạng LAN là họ dùng được. **Ai có địa chỉ này đều chạy
được pipeline và tải file lên máy bạn** — mã chỉ chặn người vô tình mò trúng cổng, không
phải hàng rào an ninh thật. Đừng mở ra internet. Không có `CHIA=1` thì server chỉ nghe
`127.0.0.1`, ngoài máy không vào được.

**Chọn kịch bản.** Ô chọn trên thanh đầu trang liệt kê mọi `vao/kich_ban*.json`. Đổi kịch
bản thì mọi thứ theo sau — cảnh, tiến độ, video cuối — đổi theo. Mỗi kịch bản ghi ra một
video riêng (`kich_ban_t2v_full.json` → `ra/video_t2v_full.mp4`) nên hai kịch bản không
đè lên nhau.

### Video collage kiểu "cắt nhanh" (dựng lại video mẫu Veo)

Làm lại video mẫu `vao/People_walking_into_freezing_tem…mp4` (Google Veo, 10 giây) hoàn toàn
trên máy này, **t2v thuần, không dùng ảnh**:

```bash
.venv/bin/python scripts/02_hoat_hinh.py --kich-ban vao/kich_ban_collage.json  --lam-lai   # 4 cảnh
.venv/bin/python scripts/02_hoat_hinh.py --kich-ban vao/kich_ban_collage2.json --lam-lai   # 6 cảnh
.venv/bin/python cong_cu/chu_collage.py          # vẽ chữ -> ra/collage_chu/*.png
.venv/bin/python cong_cu/lam_video_collage.py    # dựng -> ra/video_collage.mp4
.venv/bin/python cong_cu/lam_video_collage.py --nhac nhac.mp3   # dùng nhạc của bạn
```

Video mẫu có **10 cảnh, mỗi cảnh 0,5–1,6 giây** — không phải 4 như nhìn lướt. Nhịp cắt đo bằng
scene-detect của ffmpeg (1,38 · 3,08 · 3,96 · 5,13 · 5,92 · 7,04 · 7,79 · 8,46 · 9,75) và ghi
thẳng vào `DONG` trong `lam_video_collage.py`. Sửa bảng đó là đổi thứ tự, độ dài, chữ.

Những thứ học được khi làm:

- **LTX không vẽ nổi chữ đọc được**, nên mọi chữ (nhãn giấy xé, ô chữ HIKERS, tiêu đề máy đánh
  chữ, chữ viết tay) được vẽ bằng PIL rồi chồng lên bằng `overlay`. ffmpeg của project **không
  có `drawtext`** (bản build không kèm freetype), nên đây là cách duy nhất chứ không chỉ là cách
  đẹp hơn. Font Caveat, Kalam, Special Elite nằm ở `cong_cu/phong/`.
- **Chữ viết tay phải có mảnh giấy làm nền.** Mực nâu viết trần lên khung LTX sẽ chìm mất ở
  chỗ nền tối.
- **Đừng ghi `film grain` trong prompt.** Bảo LTX vẽ "phim" thì nó vẽ luôn cả cuộn phim:
  `collage_01` ra một dải đen có lỗ tròn rộng ~135px ở mép trái. Hạt film được thêm ở khâu dựng
  (`noise` + `vignette`) nên prompt không cần.
- **Viền LTX tự vẽ được cắt tự động**: `tu_cat()` dò cột/hàng tối ở 4 mép trên khung đầu, giữa
  và cuối đoạn dùng tới, rồi cắt giữ 16:9. Lấy **MIN** qua các khung chứ không lấy MAX — clip
  t2v hay mở đầu bằng khung tối (mép trái `collage_02` sáng 27 → 57 → 100), lấy MAX thì cắt
  nhầm clip không có viền. Viền rộng quá 20% bị coi là nội dung tối (bảng đen, đêm) và không cắt.
- **Video mẫu có tiếng liên tục** (-18 dB). Không có nhạc thì script tổng hợp tiếng gió từ nhiễu
  nâu; có nhạc của bạn thì đưa `--nhac`.

### Muốn ĐẸP thì dùng ảnh mẫu, không phải prompt

Đo được ngày 10/09/2026, cùng model LTX-2.5, cùng 1280×704, cùng 30 bước:

| | ảnh mẫu | kết quả |
|---|---|---|
| `canh_01` (i2v) | có, 2048×2048 vẽ sẵn | hoạt hình vector phẳng, viền sạch, màu bão hoà |
| `t2v_01` | không | phác thảo bút dạ, mặt trống, tỉ lệ lỏng lẻo |

Chênh lệch **không đến từ model hay độ phân giải** — mà từ việc i2v được neo vào một bức
vẽ đã đẹp sẵn. Chữ không bao giờ tả nổi một bức vẽ cụ thể. Nên quy trình cho chất lượng
cao nhất là **vẽ nhân vật bằng công cụ sinh ảnh (Gemini, 1:1) rồi để i2v làm chuyển
động**, còn t2v để dành cho cảnh không có nhân vật hoặc khi chấp nhận nét phác.

### Sáu phần của một prompt phong cách tốt

Thứ tự này quan trọng: phần **cách vẽ người** phải có, và đừng để phần chất liệu đứng
trước nuốt hết.

1. **Chất liệu + kỹ thuật** — `flat vector cartoon animation`, `oil-on-canvas`
2. **Cách vẽ người** ← thiếu phần này là hỏng: `characters with simple rounded heads,
   visible eyes and mouth, clear hands with distinct fingers`
3. **Nét** — `clean bold black outlines of even weight`
4. **Màu** — `flat saturated fill colours with no gradients`
5. **Khung hình** — `character large in frame from the knees up`
6. **Ánh sáng + nền** — `soft even lighting, simple uncluttered background`

Năm quy tắc rút ra:

- **Tả cách vẽ NGƯỜI, không chỉ tả chất liệu.** Prompt cũ tả giấy và mực rất kỹ nhưng
  không nói người trông thế nào, nên model tự bịa ra nét nguệch ngoạc.
- **Đặt nhân vật TO trong khung** — `large in frame`, `close to camera`, `from the chest up`.
  Nhân vật nhỏ thì không đủ điểm ảnh để ra hình.
- **Đừng bao giờ tả vân hay nhiễu** — `paper texture`, `grain`, `clippings`, `words floating
  around`. Model vẽ đúng thứ được bảo, và nó sẽ vẽ ra nhiễu.
- **Muốn có mặt thì phải nói** — `visible eyes and mouth`, `clear facial features`. Không
  nói thì đầu ra hình bầu dục trống.
- **Nền đơn giản** — `simple uncluttered background` để model dồn sức vào nhân vật.

Năm mẫu dựng sẵn theo đúng sáu phần này nằm ở thẻ *Phong cách tự vẽ* trên giao diện:
vector phẳng · tài liệu vẽ tay · anime cel · tranh sơn dầu · nét chì. Bấm là điền.

### Viết prompt t2v: cái bẫy "stick figure"

Đo thật ngày 10/09/2026, cùng cảnh cùng độ phân giải, chỉ đổi chữ: prompt cũ ra
**nguệch ngoạc không có chủ thể nào**, prompt mới ra người rõ đầu/thân/tay/chân. Xem
`logs/kiem/so/t2v_truoc_sau.png`. Hai nguyên nhân, đều nằm ở chữ chứ không ở model:

**1. Chuỗi phong cách tả sự lộn xộn thì model vẽ ra lộn xộn.** Bản cũ mở đầu bằng
`cream paper texture, ... handwritten cursive words floating around, taped newspaper
clippings and index cards` — bốn mươi chữ tả vân giấy và giấy tờ vụn, không tả cảnh nào.
Nó lại đứng TRƯỚC nội dung cảnh nên lấn át. Model làm đúng thứ được bảo.

**2. "Stick figure" không cho model gì để vẽ.** Vài nét que thì không có chi tiết nào để
bám, model đành phịa ra nét nguệch ngoạc. Chữ này còn bị lặp hai lần mỗi prompt — một
lần trong chuỗi phong cách, một lần trong `ghi_chu`. Cộng với `tiny`, `in the distance`,
`a search team of` thì nhân vật vừa vô định vừa bé, và vân giấy nuốt luôn đường viền.

Cách sửa, áp dụng được cho mọi phong cách:

| thay vì | viết |
|---|---|
| `stick figures` | `simple rounded human figures with a clear head, torso, arms and legs` |
| `cream paper texture` | `plain cream paper` |
| `handwritten words floating around`, `newspaper clippings` | bỏ hẳn — đó là mô tả nhiễu |
| `tiny`, `in the distance` | `large in frame`, `seen close up`, `close to camera` |
| nét mảnh | `thick black marker`, `bold confident ink strokes` |

Dấu hiệu nhận biết đã sửa đúng: **file clip nhẹ đi**. Cảnh 1 từ 10,3 MB xuống 2,9 MB —
vì không còn vân nhiễu để mã hoá, chứ không phải vì mất chi tiết.

**Phong cách tự vẽ (t2v).** Thẻ *Phong cách tự vẽ* cho gõ một câu tả nhân vật và nét vẽ;
câu đó được ghép vào **mọi** cảnh `t2v`. Đây là thứ duy nhất giữ các cảnh trông giống
nhau, vì t2v không có ảnh mẫu để neo — tả càng kỹ càng đỡ trôi, nhưng đừng mong khớp
hệt. Có sẵn vài mẫu bấm là điền. Để trống thì dùng phong cách bảng trắng mặc định. Lưu ở
`cau_hinh.phong_cach_t2v` trong kịch bản.

### Dòng lệnh

```bash
# chạy cả ba bước
.venv/bin/python cong_cu/chay_het.py

# hoặc từng bước
.venv/bin/python scripts/01_tts.py                 # tất cả cảnh có thoại
.venv/bin/python scripts/02_hoat_hinh.py           # cảnh nào chưa có clip
.venv/bin/python scripts/03_ghep.py                # nối lại + phụ đề

# làm đúng một cảnh (dùng khi thử nghiệm)
.venv/bin/python scripts/01_tts.py       --canh canh_01
.venv/bin/python scripts/02_hoat_hinh.py --canh canh_01

# làm lại đè lên file đã có
.venv/bin/python cong_cu/chay_het.py --lam-lai
```

Mặc định các script **bỏ qua** cảnh đã có kết quả, nên chạy lại sau khi bị ngắt thì nó đi
tiếp chứ không làm lại từ đầu.

---

## Hai kiểu video — chọn đúng kiểu là chênh nhau 250 lần

Trường `kieu` của mỗi cảnh quyết định cách làm hình:

| `kieu` | dùng khi | tốc độ (10 phút video) |
|---|---|---|
| **`ken_burns`** | **phim dẫn chuyện** — người đọc KHÔNG lên hình | **~3 phút** |
| `i2v` | cần chuyển động thật, không có ai nói trên hình | ~11,7 giờ |
| `s2v` | nhân vật NÓI trên hình, cần khớp miệng | ~11,7 giờ |
| `ltx` | **tự vẽ lại từ ảnh** — LTX-2.5 22B vẽ lại cảnh có chuyển động, lồng tiếng TTS | ~55 phút (5 cảnh 44s) |
| `t2v` | **tự vẽ TOÀN BỘ từ chữ** — không cần ảnh mẫu nhân vật (kiểu `thu_bangtrang_full_20s.mp4`), lồng tiếng TTS | ~5 phút/cảnh 10s |

Phim tài liệu kiểu *The Lost Archive* thì người dẫn không lên hình, **không có miệng để
khớp** — mà S2V (thứ đắt nhất) tồn tại chỉ để khớp miệng. Dùng Wan cho loại này là trả tiền
cho thứ không dùng. Ken Burns (ảnh tĩnh trôi/zoom chậm) đúng là chuẩn mực của thể loại.

Đo thật: 6 segment = 41,6s video → Ken Burns mất **1,9 giây**; cùng đoạn đó qua Wan I2V mất
~50 phút. Sáu kiểu chuyển động xoay vòng (zoom vào/ra, trôi trái/phải/lên/xuống) nên không
cảnh nào giống cảnh bên cạnh.

### Ba mức chất lượng của `ltx`

LTX-2.5 là model video open-weight mạnh nhất hiện có (Lightricks, 01/09/2026) — Wan chỉ mở
tới 2.2, Wan 2.7 chỉ chạy qua API nên không tự host được. Nên không có gì để "thay" LTX;
chỗ nâng cấp nằm ở việc chọn đúng bản LTX. Đổi tên workflow ở
`scripts/02_hoat_hinh.py` (chỗ `nap_workflow` trong nhánh `ltx`) là đổi mức:

| workflow | model | steps / CFG | tốc độ |
|---|---|---|---|
| `ltx25.json` | distilled nvfp4 (18,7 GB) | ít steps, cfg 1,0 — không guidance | nhanh nhất |
| **`ltx25_dev.json`** | **dev int8-convrot (21,5 GB)** | **30 steps, cfg 3,0/7,0** | **mặc định hiện tại** |
| `ltx25_bf16.json` | dev bf16 (39,1 GB) | 30 steps, cfg 3,0/7,0 | chậm nhất |

Bản distilled chạy `video_cfg=1.0` nghĩa là **không có classifier-free guidance** — nó bỏ
qua hẳn phần bám prompt để đổi lấy tốc độ. Đó là lý do mặc định đã chuyển sang `dev`.

Còn bf16 **không** đáng dùng dù là bản gốc không nén: 39,1 GB không lọt 32 GB VRAM của một
con 5090 nên ComfyUI phải offload sang RAM, mà 5090 lại có tensor core int8 chạy nhanh hơn
bf16 — cộng lại thì chậm hơn int8 đáng kể. Đổi lấy chênh lệch rất nhỏ, vì `int8-convrot` là
quantization do chính Lightricks hiệu chuẩn. Chia đôi qua 2 GPU cũng không cứu được: cần cài
`ComfyUI-MultiGPU`, mà nó chỉ chia **chỗ chứa** weight chứ không chia **tính toán** — các
layer vẫn chạy tuần tự, thêm PCIe giữa hai card.

Tải bộ bf16 về (nếu muốn tự so): `cong_cu/tai_ltx_bf16.sh`

Cách dùng chung: để cả phim `ken_burns`, rồi đổi riêng 5–10 cảnh cao trào sang `i2v`.
10 cảnh × 5s tốn thêm ~1 giờ, phần còn lại vẫn vài phút.

## Kịch bản dẫn chuyện có timecode

Dán nguyên định dạng có sẵn vào `vao/kich_ban_thoai.txt`:

```
[00:00 - 00:07] Segment 1
On the night of February 1st, 1959, nine experienced hikers ...
```

```bash
.venv/bin/python cong_cu/doc_kich_ban_thoai.py vao/kich_ban_thoai.txt \
    --ten "The Dyatlov Pass Mystery" --ghi
```

Nhận cả gạch ngang thường `-` lẫn gạch dài `–` `—`; tự bỏ dòng tiêu đề mục (`INTRO`,
`THE EXPEDITION`) và dòng gạch ngăn cách. Giữ lại timecode gốc ở `_timecode` để đối chiếu.
Thả thẳng file `.txt` vào giao diện cũng được — nó tự đổi.

**Timecode của bạn sẽ KHÔNG khớp, và đó là bình thường.** Chatterbox đọc nhanh hơn giọng
đọc cũ: đo được **0,73×** (6 segment ghi 57s, đọc hết trong 41,6s). Với `ken_burns`/`i2v`/`s2v`
pipeline lấy **độ dài tiếng thật** làm độ dài cảnh nên hình–tiếng–phụ đề luôn khớp nhau; chỉ
tổng thời lượng khác con số trong kịch bản. Muốn đúng thời lượng thì viết thêm chữ.

Riêng `ltx` (tự vẽ) thì ngược lại: nó **giữ đúng timecode kịch bản** — mỗi cảnh dài bằng
`_giay_du_kien` (hoặc dài hơn nếu tiếng TTS đọc chậm hơn). Phần tiếng dư ra được chèn im
lặng nên tổng video khớp đúng con số trong kịch bản.

## Ảnh cho phim dẫn chuyện

`vao/canh/canh_01.png … canh_57.png`, **16:9**, và nên **to gấp đôi khung ra**
(**1664×960** cho khung 832×480). Ken Burns zoom vào ảnh nhỏ sẽ vỡ — bộ lọc phóng to 2×
trước rồi mới zoom, nên ảnh nguồn càng lớn càng nét.

Mỗi segment một ảnh. Vì cảnh chỉ là ảnh tĩnh trôi nên ảnh **không cần có nhân vật hay khuôn
mặt**, và **không phải lo giữ nhất quán nhân vật** giữa các cảnh.


## Máy này có gì cần biết

**GPU đang có người dùng.** Hai con RTX 5090 đang chạy vLLM của anh
(`vllm-qwen38` chiếm 20,1 GB trên **cả hai** GPU vì nó chạy TP=2, và `vllm-embed`
chiếm 10,8 GB trên GPU1). Pipeline này **ghim GPU0** và chỉ dùng ~11,9 GB còn trống:

```bash
CUDA_VISIBLE_DEVICES=0 .venv/bin/python cong_cu/chay_het.py
```

Không tự tắt service của người khác — và **cũng không cần**: đo được là VRAM không phải
nút thắt, xem mục "Nhanh hơn" ở cuối.

**ComfyUI** chạy nền ở `:8188`, script tự bật khi cần:

```bash
bash cong_cu/comfy.sh len          # bật
bash cong_cu/comfy.sh tat          # tắt
bash cong_cu/comfy.sh log          # xem log
bash cong_cu/comfy.sh trang_thai
```

Nó tự chọn chế độ nạp theo VRAM còn trống: ≥24 GB → `--normalvram`,
10–24 GB → `--lowvram`, dưới nữa → `--novram`.

---

## Cấu trúc

```
vao/            file anh bỏ vào
ra/             tieng/ clip/ video_cuoi.mp4
scripts/        chung.py · 01_tts.py · 02_hoat_hinh.py · 03_ghep.py
workflows/      s2v.json (cảnh có thoại) · i2v.json (cảnh không thoại)
giao_dien/      server.py + tinh/index.html
cong_cu/        comfy.sh · chay_het.py · tai_model.sh · tao_anh_mau.py · bin/ffmpeg
models/         51 GB trọng số Wan 2.2
ComfyUI/        bản clone + venv riêng
logs/           nhật ký + số đo (do_tts.json, do_video.json)
.venv/          venv riêng cho TTS và giao diện
```

Hai venv tách nhau vì `chatterbox-tts` ghim `torch==2.6.0`, mà bản đó **không có kernel
sm_120** nên không chạy được trên RTX 5090. Đã ép lên torch 2.11+cu128 bằng
`cong_cu/ep_torch.txt` — đừng cài lại chatterbox mà bỏ file overrides đó.

---

## Vài chỗ dễ vấp

**VAE phải là bản 2.1, không phải 2.2.** `wan2.2_vae.safetensors` là VAE **48 kênh** dành
cho model TI2V-5B. Hai model 14B (S2V và I2V-A14B) dùng VAE **16 kênh**
`wan_2.1_vae.safetensors`. Cắm nhầm thì ComfyUI báo
`The size of tensor a (48) must match the size of tensor b (16)`.

**Số khung phải có dạng 4n+1.** `chung.so_khung()` lo việc này, luôn làm tròn **lên** để
không cắt mất tiếng.

**Ảnh không có mặt thì không có gì để khớp miệng.** S2V vẫn chạy và vẫn tạo chuyển động,
nhưng phần khớp miệng chỉ có ý nghĩa khi trong ảnh nhìn thấy được cái miệng.

**Thêm cảnh mới**: thêm một mục vào `kich_ban.json` và bỏ ảnh tương ứng vào `vao/canh/`.
Không phải sửa code.

---

## Nhanh hơn — theo số đo thật

> Mục này là số đo của quy trình **Wan S2V khớp miệng** (`scripts/02_hoat_hinh.py`). Xưởng video dùng
> LTX-2.5 — xem *Tốc độ vẽ* trong mục Xưởng. Chế độ Nhanh ở đó cũng chạy cfg 1, nhưng bằng model
> **distilled** (được luyện riêng để chạy cfg 1), khác hẳn việc hạ cfg của model thường như dưới đây.

Đo trên chính `canh_01` (69 khung), cùng seed, mỗi lần chỉ đổi một thứ:

| cấu hình | tổng | nhanh hơn | chất lượng |
|---|---|---|---|
| 20 bước · 832×480 · cfg 6.0 (nền) | 260,2s | — | mốc |
| **+ SageAttention** (đã bật sẵn) | **234,2s** | **1,11×** | không thấy khác |
| 12 bước | 160,1s | 1,63× | chưa kết luận được |
| 8 bước | 110,1s | 2,36× | chưa kết luận được |
| 8 bước · 640×384 | 56,0s | 4,65× | chưa kết luận được |
| **cfg 1.0** | **102,1s** | **2,29×** | **KHỚP MIỆNG YẾU HẲN — đừng dùng** |
| `--fast fp8_matrix_mult` | 296,2s | 0,88× chậm hơn | — |

### ĐỪNG hạ `cfg` xuống 1.0 để lấy tốc độ

Đây là cái bẫy dễ dính nhất, vì con số tốc độ rất hấp dẫn (**2,29×**) và **hình vẫn đẹp**
nên nhìn lướt qua tưởng không mất gì. Cái mất nằm đúng ở thứ cả dự án này tồn tại vì nó:
**biên độ cử động miệng tụt hẳn** — miệng nhỏ lại, ít thấy răng, các khung na ná nhau.
So sánh ở `logs/kiem/so/cfg_mieng.png` (hàng trên cfg 6.0, hàng dưới cfg 1.0).

Lý do 2,29×: `cfg > 1.0` bắt model chạy **hai** lượt forward mỗi bước (có điều kiện và
không điều kiện). `cfg = 1.0` bỏ lượt thứ hai. Nên đây là chuyện **nhị phân**: hạ 6.0 xuống
3.0 không nhanh hơn chút nào, vẫn hai lượt.

Muốn lấy nửa thời gian đó mà **không** mất chất lượng thì phải dùng **LoRA CFG-distill** —
loại LoRA được luyện riêng để chạy được ở `cfg=1.0`. Chưa thử.

### VRAM không phải nút thắt

**Đừng dừng vLLM để lấy VRAM.** ComfyUI stream cả 15.632 MB trọng số mỗi bước
(`dynamic VRAM loading`), nhưng việc stream được chồng lấn với tính toán qua 2 CUDA stream
nên gần như miễn phí. Bằng chứng: hạ độ phân giải làm **lượng trọng số phải stream không
đổi** mà s/bước vẫn **giảm đúng một nửa** (13,11 → 6,60). Nếu nghẽn ở VRAM thì con số đó
phải đứng yên. Nút thắt là **tính toán attention**.

Cũng vì thế `--fast fp8_matrix_mult` phản tác dụng: nó đẩy VRAM lên 11.080 MB (từ 8.560)
mà không bù lại được gì. Đã tắt.

### Hai nút chỉnh an toàn

```bash
.venv/bin/python scripts/02_hoat_hinh.py --buoc-lay 12      # ít bước hơn
.venv/bin/python scripts/02_hoat_hinh.py --rong 640 --cao 384

SAGE=0 bash cong_cu/comfy.sh len     # tắt SageAttention nếu nghi nó gây lỗi
```

"Chưa kết luận được" ở bảng trên là thật: ảnh mẫu là hình vẽ phẳng, không có kết cấu nào
để lộ nhiễu, nên các bản nhìn y hệt nhau. **Chỉ chọn được số bước khi đã có ảnh thật.**

## Bao lâu cho 25 cảnh

Cảnh dài trung bình ~4,3s, đã tính SageAttention, giữ cfg 6.0:

| cấu hình | 25 cảnh |
|---|---|
| 20 bước · 832×480 | ~1 giờ 38 phút |
| 12 bước · 832×480 | ~1 giờ 07 phút |
| 8 bước · 832×480 | ~46 phút |
| 8 bước · 640×384 | ~23 phút |

Cảnh không thoại tốn nhiều hơn cảnh có thoại vì I2V-A14B là MoE, phải nạp **hai** model
14B (high noise + low noise).

## Nếu sau này thấy chậm quá

Ba hướng đã khảo sát nhưng chưa làm, xếp theo giá trị:

1. **LoRA CFG + step distill** (~2,5 GB) — lấy được cả nửa thời gian của CFG lẫn việc giảm
   20 bước xuống 4, ước ~8–10×. Bản chính thức `lightx2v/Wan2.2-Lightning` chỉ có cho
   **I2V-A14B**; cho **S2V chưa có**, phải mượn LoRA Wan 2.1 T2V-14B — chuyển hệ, phải đo
   khớp miệng trước khi tin.
2. **Chạy 2 GPU song song** — 2× cho cả loạt. GPU1 chỉ trống 1.756 MiB vì `vllm-embed`
   chiếm 10.723 MiB; dừng embed thì GPU1 trống 12.479 MiB, bằng GPU0.
3. **TI2V-5B cho cảnh không thoại** (9,31 GB) — một model 5B vừa trọn VRAM thay cho hai
   model 14B. Ước 3–4× cho riêng cảnh B-roll. Dùng đúng `wan2.2_vae` đã tải sẵn.
