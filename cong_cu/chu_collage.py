"""Sinh TOAN BO chu cho video collage 10 canh -> ra/collage_chu/*.png"""
import random, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont
sys.path.insert(0, str(Path(__file__).resolve().parent))
import nhan_giay as NG

GOC = Path(__file__).resolve().parent.parent
RA = GOC / "ra" / "collage_chu"
MAY_CHU = GOC / "cong_cu" / "phong" / "SpecialElite-Regular.ttf"


def o_chu(chu: str, co: int = 96, hat: int = 3, font: Path | None = None) -> Image.Image:
    """Chu cai tren tung o giay vuong, moi o nghieng mot chut (kieu HIKERS trong mau)."""
    r = random.Random(hat)
    f = ImageFont.truetype(str(font or MAY_CHU), co)
    o = int(co * 1.08)
    cac = []
    for ch in chu:
        t = Image.new("RGBA", (o, o), (0, 0, 0, 0))
        d = ImageDraw.Draw(t)
        d.rectangle([2, 2, o - 3, o - 3], fill=(234, 224, 200, 255), outline=(70, 62, 52, 255), width=3)
        x0, y0, x1, y1 = f.getbbox(ch)
        d.text(((o - (x1 - x0)) / 2 - x0, (o - (y1 - y0)) / 2 - y0), ch, font=f, fill=(30, 27, 24, 255))
        cac.append(t.rotate(r.uniform(-5, 5), resample=Image.BICUBIC, expand=True))
    W = sum(t.width + 6 for t in cac) + 40
    H = max(t.height for t in cac) + 50
    lop = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    x = 20
    for t in cac:
        y = 15 + r.randint(-6, 6)
        bong = Image.new("RGBA", t.size, (0, 0, 0, 255))
        bong.putalpha(t.getchannel("A").point(lambda v: int(v * 0.45)))
        lop.alpha_composite(bong.filter(ImageFilter.GaussianBlur(5)), (x + 6, y + 8))
        lop.alpha_composite(t, (x, y))
        x += t.width + 6
    return lop


def tren_giay(im: Image.Image, hat: int = 5, le: int = 36, nghieng: float = 0.0) -> Image.Image:
    """Dat chu viet tay len manh giay xe — nen LTX toi hay roi thi chu van doc duoc."""
    r = random.Random(hat)
    pw, ph = im.width + 2 * le, im.height + 2 * le
    B = 16
    W, H = pw + 2 * B, ph + 2 * B
    tren = [(B + x, B + y) for x, y in NG._mep_rach(pw, False, 12, r)]
    duoi = [(B + x, B + ph - y) for x, y in reversed(NG._mep_rach(pw, False, 12, r))]
    phai = [(B + pw - r.randint(0, 18), B + y) for y in range(0, ph, 10)]
    trai = [(B + r.randint(0, 18), B + ph - y) for y in range(0, ph, 10)]
    mask = Image.new("L", (W, H), 0)
    ImageDraw.Draw(mask).polygon(tren + phai + duoi + trai, fill=255)
    nen = Image.blend(Image.new("RGB", (W, H), NG.GIAY), Image.effect_noise((W, H), 14).convert("RGB"), 0.06)
    lop = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    lop.paste(nen, (0, 0), mask)
    lop.alpha_composite(im, (B + le, B + le))
    bong = Image.new("RGBA", (W + 40, H + 40), (0, 0, 0, 0))
    sm = Image.new("L", (W + 40, H + 40), 0)
    sm.paste(mask.point(lambda v: int(v * 0.45)), (26, 30))
    bong.putalpha(sm.filter(ImageFilter.GaussianBlur(9)))
    bong.alpha_composite(lop, (20, 20))
    return bong.rotate(nghieng, resample=Image.BICUBIC, expand=True)


VIEC = {
    "ban_do.png":    lambda: NG.nhan("Left warmth. Dyatlov Pass.", co=52, nghieng=2.5, hat=11),
    "shelter.png":   lambda: NG.nhan("Abandoned Shelter: +20°C.", co=56, nghieng=-3, hat=7),
    "shelter2.png":  lambda: NG.nhan("Abandoned Shelter: +20°C.", co=56, nghieng=2, hat=8),
    "hikers.png":    lambda: o_chu("HIKERS", co=92),
    "tent_note.png": lambda: tren_giay(NG.viet(["Tent fabric", "slashed from inside"], co=50, nghieng=0), hat=5, le=22, nghieng=-4),
    "adversity.png": lambda: NG.nhan("THE HUMAN TEXTURE OF ADVERSITY", co=44, nghieng=-1.5, hat=21, font=MAY_CHU),
    "socks.png":     lambda: NG.nhan("Only patched socks", co=48, nghieng=3, hat=31),
    "barefoot.png":  lambda: tren_giay(NG.viet(["Completely barefoot.", "Walking miles."], co=62, nghieng=0), hat=9, le=30, nghieng=-2),
    "subzero.png":   lambda: NG.nhan("Sub-zero conditions (-30°C) recorded", co=46, nghieng=-2, hat=41),
}

if __name__ == "__main__":
    RA.mkdir(parents=True, exist_ok=True)
    for ten, lam in VIEC.items():
        im = lam(); im.save(RA / ten); print(f"  {ten:15s} {im.size[0]}x{im.size[1]}")
