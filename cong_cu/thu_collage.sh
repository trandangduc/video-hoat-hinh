#!/usr/bin/env bash
# Thu phong cach collage sepia theo ca hai duong, cung mot canh:
#   1) IMAGE : LTX 1 khung  -> vao/canh/collage_i2v.png
#   2) T2V   : LTX tu ve tu chu            -> ra/clip/collage_t2v.mp4
#   3) I2V   : LTX lam chuyen dong tu anh  -> ra/clip/collage_i2v.mp4
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
T0=$(date +%s)
P=$(python3 -c "import json;d=json.load(open('vao/kich_ban_thu_collage_t2v.json',encoding='utf-8'));print(d['cau_hinh']['phong_cach_t2v']+': '+d['canh'][0]['ghi_chu'])")

echo "=========== 1/3 IMAGE ($(date +%T)) ==========="
.venv/bin/python cong_cu/tao_anh_ltx.py --ten collage_i2v --prompt "$P" --seed 7 || { echo "LOI buoc anh"; exit 1; }

echo "=========== 2/3 T2V ($(date +%T)) ==========="
.venv/bin/python scripts/02_hoat_hinh.py --kich-ban vao/kich_ban_thu_collage_t2v.json --lam-lai || { echo "LOI buoc t2v"; exit 1; }

echo "=========== 3/3 I2V ($(date +%T)) ==========="
python3 - <<'PY'
import json
d = {
  "ten_video": "Thu collage i2v",
  "cau_hinh": {"fps": 24, "rong": 1280, "cao": 704, "giay_canh_khong_thoai": 5,
               "phu_de": False, "kieu_mac_dinh": "ltx"},
  "canh": [{"id": "collage_i2v", "anh": "collage_i2v.png", "thoai": "",
            "cam_xuc": "binh_thuong", "kieu": "ltx",
            "ghi_chu": ("slow camera push-in toward the pinned photograph, the hikers in the "
                        "photo keep trudging through the snow, torn paper edges flutter "
                        "slightly, vintage sepia collage, film grain flicker")}],
}
json.dump(d, open("vao/kich_ban_thu_collage_i2v.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
PY
.venv/bin/python scripts/02_hoat_hinh.py --kich-ban vao/kich_ban_thu_collage_i2v.json --lam-lai || { echo "LOI buoc i2v"; exit 1; }

echo "=========== HOAN TAT sau $(( $(date +%s)-T0 )) giay ==========="
