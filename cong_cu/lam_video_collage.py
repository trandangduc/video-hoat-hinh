"""Dung video collage 10 canh giong video mau: cat nhanh, chu chong len, tat den cuoi.

Nhip cat lay tu chinh video mau (scene-detect: 1.38 3.08 3.96 5.13 5.92 7.04
7.79 8.46 9.75). Chu KHONG nho LTX ve (no ve meo) ma chong PNG len bang
overlay — ffmpeg cua project khong co drawtext nen day la cach duy nhat.

  python cong_cu/lam_video_collage.py                   # tieng gio tong hop
  python cong_cu/lam_video_collage.py --nhac nhac.mp3   # dung nhac cua ban
  -> ra/video_collage.mp4   1280x720  24fps
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
FF = str(GOC / "cong_cu" / "bin" / "ffmpeg")
FP = str(GOC / "cong_cu" / "bin" / "ffprobe")
CLIP = GOC / "ra" / "clip"
CHU = GOC / "ra" / "collage_chu"
W, H, FPS = 1280, 720, 24
TAT_DEN = 0.45

# (clip, so giay, [(anh chu, x, y), ...])
DONG = [
    ("collage_01", 1.50, []),
    ("collage_02", 1.58, []),
    ("collage_05", 0.88, [("ban_do.png", 380, 36)]),
    ("collage_03", 1.17, [("shelter.png", 210, 30), ("shelter2.png", 300, 520)]),
    ("collage_06", 0.79, [("hikers.png", 50, 36), ("tent_note.png", 740, 330)]),
    ("collage_07", 1.13, [("adversity.png", 20, 20), ("socks.png", 760, 500)]),
    ("collage_04", 0.75, [("barefoot.png", 653, 24)]),
    ("collage_08", 0.67, []),
    ("collage_09", 0.54, [("subzero.png", 80, 70)]),
    ("collage_10", 1.00, []),
]

# LTX doi khi tu ve VIEN vao clip — vd collage_01 co dai phim den co lo tron
# rong ~135px o mep trai (do chu "film grain" trong prompt). Dieu nay ngau
# nhien theo clip, nen do tu dong thay vi ghi cung. Ghi tay o day de ep.
CAT: dict[str, str] = {}
TOI = 35          # diem anh toi hon muc nay la "den"
PHU = 0.70        # mot cot/hang den tren 70% chieu dai thi la vien
TRAN = 0.20       # vien rong hon 20% thi coi la NOI DUNG toi (bang den, dem) — khong cat
NHO = 60          # hep hon 60px thi la vignette mep anh (co dan khi may day vao), khong phai vien
DEN = 16          # DEN TUYET DOI: dai letterbox LTX tu ve (mong ~20-40px nhung dac den) — bat du mong
DEM = 16          # cat du them de che mep mo cua vien


def tu_cat(nguon: Path, d: float) -> str:
    """Do vien den o 4 mep tren khung dau/giua/cuoi doan dung, tra ve crop giu 16:9."""
    import numpy as np
    from PIL import Image
    tm = Path(tempfile.mkdtemp(prefix="vien_"))
    Ls, Rs, Ts, Bs = [], [], [], []
    for i, s in enumerate((0.0, d / 2, max(0.0, d - 0.05))):
        p = tm / f"{i}.png"
        chay([FF, "-v", "error", "-y", "-ss", f"{s:.3f}", "-i", str(nguon), "-frames:v", "1", str(p)])
        g = np.asarray(Image.open(p).convert("L"), dtype=float)
        h, w = g.shape
        # Khung TOI (do sang TB < 45): o canh toi, vien va noi dung toi khong tach duoc — do duoc
        # c01/c04 do sang 9-12 co 230-460 hang toi lien tiep ma deu la noi dung; c05 bi cat nham
        # 190px (zoom 1.43x). Bo qua, khong cat con hon cat sai.
        if g.mean() < 45:
            continue
        toi, den = g < TOI, g < DEN

        def rong(v: "np.ndarray", nguong: float, nho: int) -> int:
            k = 0
            while k < len(v) and v[k] >= nguong:
                k += 1
            return k if nho <= k <= len(v) * TRAN else 0

        def vien(ti: "np.ndarray", de: "np.ndarray") -> int:
            # dai phim co lo tron: toi >=70% va rong >=60px | letterbox: den >=97% va rong >=8px
            return max(rong(ti, PHU, NHO), rong(de, 0.97, 8))

        ct, cd, ht, hd = toi.mean(axis=0), den.mean(axis=0), toi.mean(axis=1), den.mean(axis=1)
        Ls.append(vien(ct, cd)); Rs.append(vien(ct[::-1], cd[::-1]))
        Ts.append(vien(ht, hd)); Bs.append(vien(ht[::-1], hd[::-1]))
    shutil.rmtree(tm, ignore_errors=True)
    # MIN chu khong phai MAX: clip LTX hay mo dau bang khung toi (hien dan tu den),
    # khung do toi ca mep nen trong giong vien. Vien THAT thi co mat o moi khung.
    if not Ls:
        return ""
    L, R, T, B = min(Ls), min(Rs), min(Ts), min(Bs)
    if not (L or R or T or B):
        return ""
    L, R, T, B = [x + DEM if x else 0 for x in (L, R, T, B)]
    x0, x1, y0, y1 = L, w - R, T, h - B
    cw, ch = x1 - x0, y1 - y0
    if cw * 9 > ch * 16:                      # con qua rong -> hep lai, can giua
        n = ch * 16 // 9
        x0 += (cw - n) // 2
        cw = n
    else:                                      # con qua cao -> thap lai, can giua
        n = cw * 9 // 16
        y0 += (ch - n) // 2
        ch = n
    return f"crop={cw - cw % 2}:{ch - ch % 2}:{x0}:{y0},"


def chay(lenh: list[str]) -> None:
    r = subprocess.run(lenh, capture_output=True, text=True)
    if r.returncode:
        sys.exit("ffmpeg loi:\n" + r.stderr[-1500:])


def do_dai(p: Path) -> float:
    r = subprocess.run([FP, "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True)
    return float(r.stdout.strip() or 0)


def hoan_thien(ghep: Path, tong: float, nhac: str | None, ra: str) -> None:
    """Hat film + vignette + tat den cuoi + tieng (nhac cua ban, hoac tieng gio tong hop)."""
    # Hat film nhe + vignette de cac clip rieng le trong nhu mot cuon phim, roi tat den.
    v = f"[0:v]noise=alls=5:allf=t,vignette=PI/5,fade=t=out:st={tong - TAT_DEN:.3f}:d={TAT_DEN}[v]"
    if nhac:
        am_vao = ["-i", nhac]
        am = (f"[1:a]atrim=0:{tong:.3f},asetpts=PTS-STARTPTS,afade=t=out:st={tong - 0.6:.3f}:d=0.6,"
              f"aformat=sample_rates=48000:channel_layouts=stereo[a]")
    else:
        am_vao = ["-f", "lavfi", "-i", f"anoisesrc=color=brown:amplitude=0.5:sample_rate=48000:duration={tong:.3f}"]
        am = (f"[1:a]lowpass=f=650,highpass=f=60,tremolo=f=0.35:d=0.55,volume=10dB,"
              f"afade=t=in:d=0.4,afade=t=out:st={tong - 0.7:.3f}:d=0.7,"
              f"aformat=sample_rates=48000:channel_layouts=stereo[a]")
    chay([FF, "-v", "error", "-y", "-i", str(ghep)] + am_vao +
         ["-filter_complex", v + ";" + am, "-map", "[v]", "-map", "[a]", "-t", f"{tong:.3f}",
          "-c:v", "libx264", "-crf", "19", "-preset", "slow", "-pix_fmt", "yuv420p",
          "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", ra])


def xem_bo_cuc(ra: Path) -> None:
    """Luoi khung GIUA cua moi canh, da cat vien va chong chu — soat bo cuc truoc khi dung."""
    from PIL import Image, ImageDraw
    tm = Path(tempfile.mkdtemp(prefix="xem_"))
    o_w, o_h = 480, 270
    luoi = Image.new("RGB", (5 * (o_w + 6), 2 * (o_h + 6)), (30, 30, 30))
    for i, (c, d, ov) in enumerate(DONG):
        nguon = CLIP / f"{c}.mp4"
        o = Image.new("RGB", (o_w, o_h), (60, 60, 60))
        if nguon.exists():
            cat = CAT[c] if c in CAT else tu_cat(nguon, d)
            p = tm / f"{i}.png"
            chay([FF, "-v", "error", "-y", "-ss", f"{d / 2:.3f}", "-i", str(nguon),
                  "-frames:v", "1", "-vf", f"{cat}scale={W}:{H}", str(p)])
            nen = Image.open(p).convert("RGBA")
            for anh, x, y in ov:
                nen.alpha_composite(Image.open(CHU / anh), (x, y))
            o = nen.convert("RGB").resize((o_w, o_h))
        dr = ImageDraw.Draw(o)
        dr.rectangle([0, 0, 150, 18], fill="black")
        dr.text((4, 4), f"{i + 1}. {c} {d:.2f}s" + ("" if nguon.exists() else " CHUA CO"), fill="yellow")
        luoi.paste(o, ((i % 5) * (o_w + 6), (i // 5) * (o_h + 6)))
    shutil.rmtree(tm, ignore_errors=True)
    ra.parent.mkdir(parents=True, exist_ok=True)
    luoi.save(ra)
    print(f"-> {ra}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--xem", nargs="?", const=str(GOC / "logs" / "kiem" / "so" / "bo_cuc_collage.png"),
                    help="chi ve luoi bo cuc 10 canh (khong dung video)")
    ap.add_argument("--nhac", help="file am thanh cua ban; khong dua thi tong hop tieng gio")
    ap.add_argument("--ra", default=str(GOC / "ra" / "video_collage.mp4"))
    a = ap.parse_args()
    if a.xem:
        return xem_bo_cuc(Path(a.xem))

    thieu = [f"clip {c}" for c, _, _ in DONG if not (CLIP / f"{c}.mp4").exists()]
    thieu += [f"chu {p}" for _, _, ov in DONG for p, _, _ in ov if not (CHU / p).exists()]
    if thieu:
        sys.exit("Thieu: " + ", ".join(sorted(set(thieu))))

    tm = Path(tempfile.mkdtemp(prefix="collage_"))
    doan = []
    for i, (c, d, ov) in enumerate(DONG):
        nguon = CLIP / f"{c}.mp4"
        if do_dai(nguon) < d:
            sys.exit(f"{c} ngan hon {d}s")
        lenh = [FF, "-v", "error", "-y", "-i", str(nguon)]
        for p, _, _ in ov:
            lenh += ["-i", str(CHU / p)]
        cat = CAT[c] if c in CAT else tu_cat(nguon, d)
        g = f"[0:v]trim=0:{d},setpts=PTS-STARTPTS,fps={FPS},{cat}scale={W}:{H},setsar=1[v0]"
        for k, (_, x, y) in enumerate(ov, 1):
            g += f";[v{k - 1}][{k}:v]overlay={x}:{y}[v{k}]"
        ra = tm / f"{i:02d}.mp4"
        lenh += ["-filter_complex", g, "-map", f"[v{len(ov)}]", "-t", str(d),
                 "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(ra)]
        chay(lenh)
        doan.append(ra)
        print(f"  canh {i + 1:2d}  {c}  {d:.2f}s  {len(ov)} chu" + (f"  [{cat.rstrip(',')}]" if cat else ""))

    ds = tm / "ds.txt"
    ds.write_text("".join(f"file '{p}'\n" for p in doan))
    ghep = tm / "ghep.mp4"
    chay([FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(ds), "-c", "copy", str(ghep)])
    tong = do_dai(ghep)

    hoan_thien(ghep, tong, a.nhac, a.ra)
    shutil.rmtree(tm, ignore_errors=True)
    print(f"-> {a.ra}  {tong:.2f}s  {Path(a.ra).stat().st_size / 1048576:.1f} MB")


if __name__ == "__main__":
    main()
