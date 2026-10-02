"""Luoi so chat luong cac cau hinh do toc do: moi hang mot cau hinh, 3 khung (dau / giua / cuoi).

  python cong_cu/luoi_so.py goc buoc20 hai_tang distilled      -> ra/do_toc_do/luoi.png
  python cong_cu/luoi_so.py --cat goc distilled                -> ra/do_toc_do/luoi_cat.png (cat 1/3 giua, 100%)

Nhan moi hang: ten + so giay ve (doc tu logs/do_toc_do.jsonl, lay lan do moi nhat).
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import lam_video_collage as LV  # noqa: E402

RA = GOC / "ra" / "do_toc_do"
MOC = (0.6, 2.5, 4.4)            # giay — clip do dai 5.04 s
O_W, O_H, NHAN = 480, 264, 150


def so_giay() -> dict:
    kq = {}
    for dong in (GOC / "logs" / "do_toc_do.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(dong)
            kq[d["ten"]] = d.get("giay_ve")
        except Exception:
            pass
    return kq


def khung(mp4: Path, t: float) -> Image.Image:
    anh = subprocess.run([LV.FF, "-v", "error", "-ss", str(t), "-i", str(mp4), "-frames:v", "1",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True, check=True).stdout
    from io import BytesIO
    return Image.open(BytesIO(anh)).convert("RGB")


def main() -> None:
    cat = "--cat" in sys.argv
    ten = [x for x in sys.argv[1:] if not x.startswith("--")]
    ten = [t for t in ten if (RA / f"{t}.mp4").exists()]
    if not ten:
        sys.exit("Khong co mp4 nao trong ra/do_toc_do cho cac ten da cho.")
    giay = so_giay()
    goc = giay.get("goc")
    font = ImageFont.truetype(str(GOC / "cong_cu" / "phong" / "IBMPlexMono-SemiBold.ttf"), 22)
    nho = ImageFont.truetype(str(GOC / "cong_cu" / "phong" / "IBMPlexMono-SemiBold.ttf"), 17)
    bang = Image.new("RGB", (NHAN + O_W * len(MOC), O_H * len(ten)), (18, 18, 18))
    ve = ImageDraw.Draw(bang)
    for h, t in enumerate(ten):
        y = h * O_H
        g = giay.get(t)
        ve.text((12, y + 14), t, font=font, fill=(240, 240, 240))
        if g:
            ve.text((12, y + 48), f"{g:.0f} s", font=nho, fill=(190, 190, 190))
            if goc and t != "goc":
                ve.text((12, y + 72), f"x{goc / g:.2f}", font=nho, fill=(120, 220, 140))
        for c, m in enumerate(MOC):
            im = khung(RA / f"{t}.mp4", m)
            if cat:                                   # 1/3 giua o 100% do phan giai -> thay chi tiet net
                w, hh = im.width // 3, im.height // 3
                im = im.crop((w, hh, 2 * w, 2 * hh))
            bang.paste(im.resize((O_W, O_H), Image.LANCZOS), (NHAN + c * O_W, y))
        ve.line([(0, y + O_H - 1), (bang.width, y + O_H - 1)], fill=(60, 60, 60))
    ra = RA / ("luoi_cat.png" if cat else "luoi.png")
    bang.save(ra)
    print(ra)


if __name__ == "__main__":
    main()
