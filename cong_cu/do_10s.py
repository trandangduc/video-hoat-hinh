"""Do thoi gian ve MOT canh 10 giay (249 khung) theo tung cach ve cua Xuong — de bao nguoi dung.

  python cong_cu/do_10s.py nhanh_t2v nhanh_khung_dau
  -> ra/do_10s/<ten>.mp4 + logs/do_10s.jsonl

Moi cach ve chay mot luot "nap" ngan (9 khung) truoc: so do la luc model DA nap san; thoi gian nap ghi rieng.
Chuan 10 giay da do ngay 10/09 (logs/xuong_cau_hinh.json bang_phut), giu nhan vat do trong
cong_cu/thu_giu_nhan_vat.py — khong chay lai o day.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import du_an as DA  # noqa: E402

RA = GOC / "ra" / "do_10s"
LOG = GOC / "logs" / "do_10s.jsonl"
PROMPT = ("flat 2D cartoon animation, thick black outlines: a man in a conical straw hat and a pink floral shirt "
          "walks through deep snow in a mountain pass at dawn, leaving footprints; slow tracking shot")
ANH = GOC / "vao" / "canh" / "canh_01.png"
CACH = {  # ten -> (che_do, anh khung dau)
    "nhanh_t2v": ("nhanh", None),
    "nhanh_khung_dau": ("nhanh", ANH),
    "chuan_t2v": ("chuan", None),
}


def ve(ten: str, k: int) -> float:
    cd, anh = CACH[ten]
    t = time.time()
    DA.ve_mot_clip(PROMPT, k, 4242, anh, RA / f"{ten}_{k}.mp4", f"do_10s/{ten}", cd)
    return time.time() - t


def main() -> None:
    RA.mkdir(parents=True, exist_ok=True)
    k = DA.so_khung(10)
    for ten in sys.argv[1:]:
        if ten not in CACH:
            print(json.dumps({"ten": ten, "loi": "khong co cach nay"}), flush=True)
            continue
        nap = ve(ten, 9)                      # nap model (+ doi model neu can)
        try:
            giay, loi = ve(ten, k), ""
        except Exception as e:
            giay, loi = None, str(e)[:400]
        kq = {"ten": ten, "khung": k, "giay_ve": round(giay, 1) if giay else None,
              "phut": round(giay / 60, 1) if giay else None, "luot_nap_9_khung": round(nap, 1),
              "loi": loi, "luc": time.strftime("%H:%M:%S")}
        print(json.dumps(kq, ensure_ascii=False), flush=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(kq, ensure_ascii=False) + "\n")
    print("XONG DO 10S", flush=True)


if __name__ == "__main__":
    main()
