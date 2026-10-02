"""Sinh 3 anh placeholder cho kich ban mau.

Muc dich DUY NHAT la de chay thu pipeline khi chua co anh that. Hai canh dau
co mot khuon mat ve don gian -- can co MIENG thi moi nhin ra duoc S2V khop
mieng hay khong; anh phong canh tron thi khong kiem duoc gi.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

GOC = Path(__file__).resolve().parent.parent
RA = GOC / "vao" / "canh"
W, H = 832, 480


def nen(tu: tuple[int, int, int], den: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(img)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(int(tu[i] + (den[i] - tu[i]) * t) for i in range(3)))
    return img


def khuon_mat(img: Image.Image, tam: tuple[int, int], cao: int,
              da: tuple[int, int, int], toc: tuple[int, int, int]) -> None:
    d = ImageDraw.Draw(img)
    cx, cy = tam
    rx, ry = int(cao * 0.42), cao // 2

    # co va vai
    d.polygon([(cx - rx * 1.9, H), (cx - rx * 0.75, cy + ry * 0.75),
               (cx + rx * 0.75, cy + ry * 0.75), (cx + rx * 1.9, H)],
              fill=tuple(max(0, c - 55) for c in da))
    # dau
    d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=da)
    # toc
    d.chord([cx - rx, cy - ry, cx + rx, cy + ry * 0.55], 180, 360, fill=toc)
    # mat
    for s in (-1, 1):
        ex = cx + s * int(rx * 0.38)
        ey = cy - int(ry * 0.12)
        d.ellipse([ex - 15, ey - 9, ex + 15, ey + 9], fill=(250, 250, 252))
        d.ellipse([ex - 6, ey - 6, ex + 6, ey + 6], fill=(38, 42, 52))
    # long may
    for s in (-1, 1):
        ex = cx + s * int(rx * 0.38)
        d.line([(ex - 17, cy - int(ry * 0.34)), (ex + 17, cy - int(ry * 0.38))],
               fill=toc, width=5)
    # mui
    d.line([(cx, cy - int(ry * 0.02)), (cx - 5, cy + int(ry * 0.2))],
           fill=tuple(max(0, c - 40) for c in da), width=4)
    # MIENG -- phan quan trong nhat: S2V se lam no cu dong theo audio
    my = cy + int(ry * 0.44)
    d.ellipse([cx - 40, my - 15, cx + 40, my + 15], fill=(150, 72, 78))
    d.ellipse([cx - 34, my - 9, cx + 34, my + 5], fill=(92, 40, 46))


def phong_canh(img: Image.Image) -> None:
    d = ImageDraw.Draw(img)
    # mat troi
    d.ellipse([600, 120, 700, 220], fill=(255, 214, 150))
    # day nha cao tang
    x = 40
    cao_nha = [210, 300, 170, 340, 250, 380, 200, 310, 260, 350, 190]
    for i, c in enumerate(cao_nha):
        w = 52 + (i % 3) * 16
        toi = 46 + (i % 4) * 10
        d.rectangle([x, H - c, x + w, H], fill=(toi, toi + 6, toi + 18))
        for wy in range(H - c + 18, H - 20, 26):
            for wx in range(x + 9, x + w - 12, 20):
                if (wx + wy) % 3:
                    d.rectangle([wx, wy, wx + 8, wy + 12], fill=(255, 198, 120))
        x += w + 14


def main() -> None:
    RA.mkdir(parents=True, exist_ok=True)

    a = nen((38, 44, 68), (96, 74, 92))
    khuon_mat(a, (416, 250), 300, (226, 186, 158), (52, 40, 44))
    a.filter(ImageFilter.SMOOTH).save(RA / "canh_01.png")

    b = nen((44, 58, 104), (232, 148, 98))
    phong_canh(b)
    b.filter(ImageFilter.SMOOTH).save(RA / "canh_02.png")

    c = nen((30, 52, 58), (120, 132, 108))
    khuon_mat(c, (300, 262), 280, (214, 174, 146), (40, 34, 36))
    c.filter(ImageFilter.SMOOTH).save(RA / "canh_03.png")

    for p in sorted(RA.glob("canh_0*.png")):
        print(f"  {p.name}  {Image.open(p).size}")


if __name__ == "__main__":
    main()
