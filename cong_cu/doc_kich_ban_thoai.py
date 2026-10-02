"""Doi kich ban DAN CHUYEN (co timecode) -> vao/kich_ban.json cua pipeline.

Nhan dung dinh dang anh dang viet:

    [00:00 - 00:07] Segment 1
    On the night of February 1st, 1959, nine experienced hikers ...

Dong TIEU DE mucA (INTRO, THE EXPEDITION...) va dong gach ngang bi bo qua.
Chap nhan ca dau gach ngang thuong '-' lan gach dai '–' '—'.

  python cong_cu/doc_kich_ban_thoai.py vao/kich_ban_thoai.txt
  python cong_cu/doc_kich_ban_thoai.py vao/kich_ban_thoai.txt --kieu i2v --ghi
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))

# [00:00 - 00:07] Segment 1     (gach ngang kieu gi cung duoc)
RX = re.compile(
    r"^\s*\[\s*(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})\s*\]\s*"
    r"(?:Segment\s*)?(\d+)?\s*$", re.I)


def giay(phut: str, gy: str) -> float:
    return int(phut) * 60 + int(gy)


def doc(duong: Path) -> list[dict]:
    dong = duong.read_text(encoding="utf-8").splitlines()
    canh, hien = [], None
    for d in dong:
        m = RX.match(d)
        if m:
            if hien:
                canh.append(hien)
            hien = {"tu": giay(m.group(1), m.group(2)),
                    "den": giay(m.group(3), m.group(4)),
                    "so": int(m.group(5)) if m.group(5) else len(canh) + 1,
                    "chu": []}
            continue
        d = d.strip()
        if not d or set(d) <= set("_-–—=*"):      # dong ngan cach
            continue
        if hien is None:                            # chua vao segment nao
            continue
        # dong TIEU DE MUC: viet hoa het va khong co dau cau ket
        if d == d.upper() and len(d.split()) <= 6 and not d.endswith((".", "?", "!")):
            continue
        hien["chu"].append(d)
    if hien:
        canh.append(hien)
    for c in canh:
        c["chu"] = " ".join(c["chu"]).strip()
    return [c for c in canh if c["chu"]]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("nguon")
    p.add_argument("--kieu", choices=["ken_burns", "i2v", "s2v"], default="ken_burns",
                   help="cach lam hinh cho MOI canh; sua tung canh sau cung duoc")
    p.add_argument("--ten", default="Video")
    p.add_argument("--ghi", action="store_true", help="ghi de vao/kich_ban.json")
    a = p.parse_args()

    canh = doc(Path(a.nguon))
    if not canh:
        print("Khong doc duoc segment nao. Kiem lai dinh dang [mm:ss - mm:ss].",
              file=sys.stderr)
        raise SystemExit(1)

    ra = {
        "ten_video": a.ten,
        "cau_hinh": {"fps": 16, "rong": 832, "cao": 480,
                     "giay_canh_khong_thoai": 5, "phu_de": True,
                     "kieu_mac_dinh": a.kieu},
        "canh": [{
            "id": f"canh_{c['so']:02d}",
            "anh": f"canh_{c['so']:02d}.png",
            "thoai": c["chu"],
            "cam_xuc": "trang_trong",
            "kieu": a.kieu,
            "ghi_chu": "",
            "_timecode": f"{c['tu']//60:02d}:{c['tu']%60:02d}-{c['den']//60:02d}:{c['den']%60:02d}",
            "_giay_du_kien": round(c["den"] - c["tu"], 1),
        } for c in canh],
    }

    tong = sum(c["_giay_du_kien"] for c in ra["canh"])
    print(f"Doc duoc {len(canh)} segment, tong theo timecode: "
          f"{tong:.0f}s = {tong/60:.1f} phut")
    print(f"  ngan nhat {min(c['_giay_du_kien'] for c in ra['canh']):.0f}s  ·  "
          f"dai nhat {max(c['_giay_du_kien'] for c in ra['canh']):.0f}s  ·  "
          f"trung binh {tong/len(canh):.1f}s")
    print(f"  kieu lam hinh: {a.kieu}")

    dich = GOC / "vao" / ("kich_ban.json" if a.ghi else "kich_ban_thu.json")
    dich.write_text(json.dumps(ra, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {dich.relative_to(GOC)}")
    if not a.ghi:
        print("     (them --ghi de ghi thang vao vao/kich_ban.json)")


if __name__ == "__main__":
    main()
