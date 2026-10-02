"""Do do BAT ON cua mot clip bang so, thay vi nhin bang mat.

Y tuong: video on dinh thi hai khung lien tiep chi khac nhau it va khac deu.
Khi model bat dau "bia" ra thu moi giua chung thi do lech nhay vot o vai cho
-- do la cai mat nguoi doc ra thanh "nhieu" hay "vat la xuat hien".

  python cong_cu/do_nhieu.py <clip.mp4> [clip2.mp4 ...]
"""
from __future__ import annotations
import subprocess, sys, tempfile, os, glob
import numpy as np
from PIL import Image

F = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bin", "ffmpeg")


def do(clip: str, moi: int = 2) -> dict:
    d = tempfile.mkdtemp()
    subprocess.run([F, "-y", "-v", "error", "-i", clip,
                    "-vf", f"select='not(mod(n\\,{moi}))',scale=320:-1",
                    "-vsync", "0", os.path.join(d, "%04d.png")], capture_output=True)
    ps = sorted(glob.glob(os.path.join(d, "*.png")))
    if len(ps) < 3:
        return {}
    a = [np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255 for p in ps]
    lech = np.array([np.abs(a[i + 1] - a[i]).mean() for i in range(len(a) - 1)])
    for p in ps:
        os.unlink(p)
    os.rmdir(d)
    # gia toc: doi lech DOT NGOT giua hai cap khung lien tiep -> dau hieu bat on
    giat = np.abs(np.diff(lech))
    return {"so_khung": len(ps),
            "lech_tb": lech.mean(),
            "lech_dinh": lech.max(),
            "giat_tb": giat.mean(),
            "giat_dinh": giat.max(),
            "so_cho_giat": int((giat > giat.mean() + 3 * giat.std()).sum())}


if __name__ == "__main__":
    print(f"{'clip':<30}{'khung':>6}{'lech tb':>9}{'lech dinh':>11}"
          f"{'giat tb':>9}{'giat dinh':>11}{'cho giat':>10}")
    for c in sys.argv[1:]:
        r = do(c)
        if not r:
            print(f"  {os.path.basename(c)}: khong doc duoc"); continue
        print(f"{os.path.basename(c):<30}{r['so_khung']:>6}{r['lech_tb']:>9.4f}"
              f"{r['lech_dinh']:>11.4f}{r['giat_tb']:>9.4f}{r['giat_dinh']:>11.4f}"
              f"{r['so_cho_giat']:>10}")
    print("\n  'cho giat' = so lan do lech nhay vot bat thuong (>3 do lech chuan).")
    print("  Cang cao = cang co vat la nhay ra giua chung.")
