"""So video cua ta voi video mau tai CUNG moc thoi gian.

Moi o la mot cap: tren = mau, duoi = cua ta. Dung de nhin xem nhip cat,
bo cuc va chu co khop khong.

  python cong_cu/so_voi_mau.py                                  # mac dinh
  python cong_cu/so_voi_mau.py --ta ra/video_collage.mp4 --buoc 1.0
  -> logs/kiem/so/so_voi_mau.png
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw

GOC = Path(__file__).resolve().parent.parent
FF = str(GOC / "cong_cu" / "bin" / "ffmpeg")
FP = str(GOC / "cong_cu" / "bin" / "ffprobe")


def do_dai(p: Path) -> float:
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def khung(p: Path, t: float, rong: int, tm: Path) -> Image.Image:
    ra = tm / f"{p.stem}_{t:.2f}.png"
    subprocess.run([FF, "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(p),
                    "-frames:v", "1", "-vf", f"scale={rong}:-2", str(ra)], check=True)
    return Image.open(ra).convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mau", default=str(next((GOC / "vao").glob("People_walking*.mp4"))))
    ap.add_argument("--ta", default=str(GOC / "ra" / "video_collage.mp4"))
    ap.add_argument("--buoc", type=float, default=1.0, help="khoang cach giua cac moc, giay")
    ap.add_argument("--cot", type=int, default=5)
    ap.add_argument("--ra", default=str(GOC / "logs" / "kiem" / "so" / "so_voi_mau.png"))
    a = ap.parse_args()

    mau, ta = Path(a.mau), Path(a.ta)
    tong = min(do_dai(mau), do_dai(ta))
    moc = []
    t = a.buoc / 2
    while t < tong - 0.05:
        moc.append(t)
        t += a.buoc

    o_rong = 320
    tm = Path(tempfile.mkdtemp(prefix="so_mau_"))
    cap = []
    for t in moc:
        m, n = khung(mau, t, o_rong, tm), khung(ta, t, o_rong, tm)
        o = Image.new("RGB", (o_rong, m.height + n.height + 4), "white")
        o.paste(m, (0, 0))
        o.paste(n, (0, m.height + 4))
        d = ImageDraw.Draw(o)
        d.rectangle([0, 0, 58, 16], fill="black")
        d.text((4, 3), f"{t:.2f}s", fill="yellow")
        d.rectangle([0, m.height + 4, 30, m.height + 20], fill="black")
        d.text((4, m.height + 7), "TA", fill="cyan")
        cap.append(o)

    hang = -(-len(cap) // a.cot)
    oh = cap[0].height
    luoi = Image.new("RGB", (a.cot * (o_rong + 6), hang * (oh + 6)), (40, 40, 40))
    for i, o in enumerate(cap):
        luoi.paste(o, ((i % a.cot) * (o_rong + 6), (i // a.cot) * (oh + 6)))
    Path(a.ra).parent.mkdir(parents=True, exist_ok=True)
    luoi.save(a.ra)
    print(f"-> {a.ra}  {len(moc)} moc, tren = mau, duoi = TA")


if __name__ == "__main__":
    main()
