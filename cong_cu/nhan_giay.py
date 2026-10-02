"""Ve chu viet tay cho video collage — LTX khong ve noi chu doc duoc.

Hai kieu, deu la PNG trong suot de ffmpeg chong len clip:
  nhan   : dai giay xe mau kem, mep rach, bong do nhe, chu muc o giua
  viet   : chu viet thang len giay (khong co nen), co the nhieu dong

  python cong_cu/nhan_giay.py nhan  "Abandoned Shelter: +20°C."   ra/collage_chu/shelter.png
  python cong_cu/nhan_giay.py viet  "Completely barefoot.|Walking miles."  ra/collage_chu/barefoot.png
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

GOC = Path(__file__).resolve().parent.parent
FONT = GOC / "cong_cu" / "phong" / "Caveat.ttf"
MUC = (38, 34, 30)          # muc nau den
GIAY = (236, 227, 205)      # giay kem cu


def _font(co: int, duong: Path | None = None) -> ImageFont.FreeTypeFont:
    f = ImageFont.truetype(str(duong or FONT), co)
    try:
        f.set_variation_by_name("SemiBold")   # Caveat la font bien the
    except Exception:
        pass
    return f


def _mep_rach(dai: int, doc: bool, bien: int, r: random.Random) -> list[tuple[int, int]]:
    """Duong mep rach: di doc theo mot canh, lech ngau nhien toi da `bien` px."""
    diem, t = [], 0
    while t < dai:
        diem.append((t, r.randint(0, bien)))
        t += r.randint(6, 18)
    diem.append((dai, r.randint(0, bien)))
    return diem


def nhan(chu: str, co: int = 64, nghieng: float = -3.0, hat: int = 7,
         font: Path | None = None) -> Image.Image:
    r = random.Random(hat)
    f = _font(co, font)
    x0, y0, x1, y1 = f.getbbox(chu)
    tw, th = x1 - x0, y1 - y0
    pw, ph = tw + 90, th + 56
    B = 14                                   # bien cho mep rach
    W, H = pw + 2 * B, ph + 2 * B

    # hinh dai giay: tren va duoi rach, hai dau rach manh hon
    tren = [(B + x, B + y) for x, y in _mep_rach(pw, False, 9, r)]
    duoi = [(B + x, B + ph - y) for x, y in reversed(_mep_rach(pw, False, 9, r))]
    phai = [(B + pw - r.randint(0, 16), B + y) for y in range(0, ph, 10)]
    trai = [(B + r.randint(0, 16), B + ph - y) for y in range(0, ph, 10)]
    hinh = tren + phai + duoi + trai

    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(hinh, fill=255)

    # nen giay co van nhe + toi dan ve mep
    giay = Image.new("RGB", (W, H), GIAY)
    px = giay.load()
    for y in range(H):
        for x in range(W):
            n = r.randint(-9, 9)
            c = GIAY
            px[x, y] = (c[0] + n, c[1] + n, c[2] + n - 2)
    giay = giay.filter(ImageFilter.GaussianBlur(0.6))
    toi = mask.filter(ImageFilter.GaussianBlur(6))
    vien = Image.new("RGB", (W, H), (190, 176, 150))
    giay = Image.composite(giay, vien, toi)

    lop = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lop.paste(giay, (0, 0), mask)
    d = ImageDraw.Draw(lop)
    d.text((B + 45 - x0, B + 28 - y0), chu, font=f, fill=MUC + (240,))

    # bong do + nghieng
    bong = Image.new("RGBA", (W + 40, H + 40), (0, 0, 0, 0))
    sm = Image.new("L", (W + 40, H + 40), 0)
    sm.paste(mask.point(lambda v: v * 0.45), (26, 30))
    bong.putalpha(sm.filter(ImageFilter.GaussianBlur(8)))
    bong.alpha_composite(lop, (20, 20))
    return bong.rotate(nghieng, resample=Image.BICUBIC, expand=True)


def viet(dong: list[str], co: int = 78, nghieng: float = -2.0,
         font: Path | None = None) -> Image.Image:
    f = _font(co, font)
    cao_dong = int(co * 1.15)
    rong = max(f.getbbox(s)[2] for s in dong) + 40
    lop = Image.new("RGBA", (rong, cao_dong * len(dong) + 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(lop)
    for i, s in enumerate(dong):
        d.text((20, 20 + i * cao_dong), s, font=f, fill=MUC + (235,))
    # muc hoi loang vao giay
    lop = lop.filter(ImageFilter.GaussianBlur(0.4))
    return lop.rotate(nghieng, resample=Image.BICUBIC, expand=True)


def main() -> None:
    kieu, chu, ra = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    ra.parent.mkdir(parents=True, exist_ok=True)
    im = nhan(chu) if kieu == "nhan" else viet(chu.split("|"))
    im.save(ra)
    print(f"-> {ra}  {im.size[0]}x{im.size[1]}")


if __name__ == "__main__":
    main()
