#!/usr/bin/env python3
"""Do do NET cua vung noi dung trong clip, so voi anh goc thu nho cung co.

Dung de tra loi "co that su net hon khong" bang so, thay vi nhin bang mat.
Do net = phuong sai Laplacian; cang cao cang nhieu canh sac.

  python cong_cu/do_net.py ra/clip/canh_01.mp4 vao/canh/canh_01.png
"""
import sys
import numpy as np
from PIL import Image
from numpy.lib.stride_tricks import sliding_window_view


def do_net(a: Image.Image) -> float:
    g = np.asarray(a.convert("L"), dtype=np.float64)
    k = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype=np.float64)
    return ((sliding_window_view(g, (3, 3)) * k).sum(axis=(2, 3))).var()


def khung_giua(mp4: str) -> Image.Image:
    import subprocess, tempfile, os
    from pathlib import Path
    ff = str(Path(__file__).resolve().parent / "bin" / "ffmpeg")
    ra = tempfile.mktemp(suffix=".png")
    subprocess.run([ff, "-v", "error", "-y", "-i", mp4,
                    "-vf", r"select=eq(n\,80)", "-vframes", "1", ra], check=True)
    im = Image.open(ra).convert("RGB").copy()
    os.unlink(ra)
    return im


def main() -> None:
    mp4, goc = sys.argv[1], sys.argv[2]
    kh = khung_giua(mp4)
    # Anh mau vuong -> vung noi dung la o vuong giua khung, canh = chieu cao.
    c = kh.height
    x = (kh.width - c) // 2
    vung = kh.crop((x, 0, x + c, c))
    g = Image.open(goc).convert("RGB").resize((c, c), Image.LANCZOS)
    n_ra, n_goc = do_net(vung), do_net(g)
    print(f"{mp4}")
    print(f"  khung          : {kh.width}x{kh.height}   vung noi dung {c}x{c}")
    print(f"  do net model   : {n_ra:8.1f}")
    print(f"  do net anh goc : {n_goc:8.1f}  (cung co {c}x{c})")
    print(f"  model mem hon  : {n_goc / n_ra:.2f}x")


if __name__ == "__main__":
    main()
