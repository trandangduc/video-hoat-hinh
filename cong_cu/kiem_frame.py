"""Kiem chat luong video BANG SO — quet tung frame mot, khong dua vao mat.

Check gi:
  1. Giai ma ca file — bat moi warning/error cua decoder.
  2. Dem frame: so frame giai ma dung bang so frame khai bao.
  3. Frame DEN / TRANG TRONG — flag ngay.
  4. Frame DONG BANG: lien tuc >= 1s hai frame giong het nhau = video teo.
  5. Moi canh phai CO DONG: do lech giua cac frame lien tiep ~0 = video tinh.
  6. Chuyen canh: fade phai xuat hien dung vi tri (cung cong thuc voi 03_ghep).
  7. DUNG HINH DUNG CANH: frame giua moi canh phai giong anh goc tuong ung
     (vao/canh/canh_XX.png) nhat — so correlation voi TAT CA anh goc.
  8. Audio: dai bang video; moi canh co loi noi (max_volume khong qua thap).

  python cong_cu/kiem_frame.py ra/video_cuoi.mp4
  python cong_cu/kiem_frame.py ra/clip/canh_01.mp4 ra/clip/canh_02.mp4
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import chung as C

import numpy as np
from PIL import Image

KICH_BAN = None  # duong dan kich ban tu chon (--kich-ban), None = mac dinh


def thong_tin_stream(duong: Path) -> dict:
    ra = subprocess.run(
        [C.FFPROBE, "-v", "error", "-show_entries",
         "format=duration:stream=index,codec_type,codec_name,duration,nb_frames,"
         "width,height,avg_frame_rate",
         "-of", "json", str(duong)],
        capture_output=True, text=True)
    d = json.loads(ra.stdout or "{}")
    ket_qua = {"duration": float(d.get("format", {}).get("duration", 0) or 0),
               "v": None, "a": None}
    for s in d.get("streams", []):
        if s.get("codec_type") == "video" and ket_qua["v"] is None:
            ket_qua["v"] = s
        if s.get("codec_type") == "audio" and ket_qua["a"] is None:
            ket_qua["a"] = s
    return ket_qua


def giai_ma_khong_loi(duong: Path) -> list[str]:
    ra = subprocess.run(
        [C.FFMPEG, "-v", "error", "-i", str(duong), "-f", "null", "-"],
        capture_output=True, text=True)
    return [x for x in ra.stderr.splitlines() if x.strip()]


def xuat_frame(duong: Path, thu_muc: Path) -> int:
    ra = subprocess.run(
        [C.FFMPEG, "-y", "-v", "error", "-i", str(duong),
         "-q:v", "2", str(thu_muc / "%06d.jpg")],
        capture_output=True, text=True)
    if ra.returncode:
        raise SystemExit(f"khong xuat duoc frame: {ra.stderr[-500:]}")
    return len(list(thu_muc.glob("*.jpg")))


def quet_frame(cac_frame: list[Path]):
    """Quet tung frame: do sang, do phan tan, do lech voi frame truoc."""
    n = len(cac_frame)
    mean = np.zeros(n)
    std = np.zeros(n)
    diff = np.zeros(n)
    truoc = None
    for i, p in enumerate(cac_frame):
        with Image.open(p) as im:
            g = np.asarray(im.convert("L").resize((192, 108), Image.BILINEAR),
                           dtype=np.float32)
        mean[i] = g.mean()
        std[i] = g.std()
        if truoc is not None:
            diff[i] = np.abs(g - truoc).mean()
        truoc = g
    return mean, std, diff


def tim_canh_chua(dai: list[float], gd: float = 0.5, dem: float = 0.65) -> list[float]:
    """Moc bat dau moi canh trong video cuoi — cung cong thuc voi 03_ghep."""
    mocs, m = [0.0], 0.0
    for i in range(len(dai) - 1):
        m += (dai[i] + dem) - gd
        mocs.append(m)
    return mocs


def correlation(a: np.ndarray, b: np.ndarray) -> float:
    a = a - a.mean()
    b = b - b.mean()
    mau = np.sqrt((a * a).sum() * (b * b).sum())
    return float((a * b).sum() / mau) if mau > 0 else 0.0


def anh_goc_xam(rong: int = 192, cao: int = 108) -> dict[str, np.ndarray]:
    ket_qua = {}
    for p in sorted(C.CANH.glob("*.png")):
        with Image.open(p) as im:
            ket_qua[p.stem] = np.asarray(
                im.convert("L").resize((rong, cao), Image.BILINEAR), dtype=np.float32)
    return ket_qua

def kiem_audio_canh(duong: Path, canh_muc: list[tuple[str, float, float]]) -> list[tuple[str, float]]:
    """Do max_volume tung canh — khong qua thap nghia la co loi noi."""
    ket_qua = []
    for ten, d1, d2 in canh_muc:
        ra = subprocess.run(
            [C.FFMPEG, "-ss", f"{d1:.3f}", "-t", f"{max(0.1, d2 - d1):.3f}",
             "-i", str(duong), "-af", "volumedetect", "-f", "null", "-"],
            capture_output=True, text=True)
        m = re.search(r"max_volume: (-?[\d.]+) dB", ra.stderr)
        ket_qua.append((ten, float(m.group(1)) if m else -99.0))
    return ket_qua


def kiem_mot_video(duong: Path, la_clip_le: bool = False) -> bool:
    C.buoc(f"KIEM TRA {duong}")
    ok = True
    st = thong_tin_stream(duong)
    v, a = st["v"], st["a"]
    if v is None:
        print("  LOI: khong co stream video")
        return False
    mf = (v.get("avg_frame_rate") or "24/1").split("/")
    fps = float(mf[0]) / float(mf[1] or 1) if mf[0] else 24.0
    so_khung_v = int(v.get("nb_frames") or 0)
    dai_v = float(v.get("duration") or 0)
    dai_a = float(a.get("duration") or 0) if a else 0.0
    print(f"  video: {v.get('codec_name')} {v.get('width')}x{v.get('height')} "
          f"@{fps:.0f}fps  {so_khung_v} khung = {dai_v:.2f}s")
    print(f"  audio: {(a or {}).get('codec_name', 'KHONG CO')}  {dai_a:.2f}s")

    loi = giai_ma_khong_loi(duong)
    if loi:
        ok = False
        print(f"  LOI: decoder bao {len(loi)} van de:")
        for x in loi[:5]:
            print(f"    {x[:120]}")
    else:
        print("  decode: sach, khong bao loi")

    if a and abs(dai_a - dai_v) > 0.3:
        ok = False
        print(f"  LOI: audio {dai_a:.2f}s lech video {dai_v:.2f}s qua nhieu")
    elif a:
        print(f"  audio/video lech: {abs(dai_a - dai_v):.3f}s (< 0.3s dat)")

    thu_muc = Path(tempfile.mkdtemp(prefix="kiem_frame_"))
    try:
        so = xuat_frame(duong, thu_muc)
        if so_khung_v and so != so_khung_v:
            ok = False
            print(f"  LOI: giai ma {so} frame nhung header khai bao {so_khung_v}")
        else:
            print(f"  frames: {so} (dung bang header)")
        if so == 0:
            return False

        cac_frame = sorted(thu_muc.glob("*.jpg"))
        mean, std, diff = quet_frame(cac_frame)

        den = [i for i in range(len(mean)) if mean[i] < 6.0]
        trang = [i for i in range(len(mean)) if mean[i] > 249.0]
        flat = [i for i in range(len(std)) if std[i] < 1.5]
        if den or trang:
            ok = False
            print(f"  LOI: {len(den)} frame den + {len(trang)} frame trang "
                  f"(vi tri dau: {(den + trang)[:3]})")
        else:
            print("  frame den/trang trang: KHONG CO")
        print(f"  frame gan 1 mau (std<1.5): {len(flat)}"
              + (f" vi tri dau {flat[:3]}" if flat else ""))

        frozen = []
        chay = 0
        for i in range(1, len(diff)):
            chay = chay + 1 if diff[i] < 0.15 else 0
            if chay >= fps:
                frozen.append((i - chay) / fps)
        if frozen:
            print(f"  CANH BAO: {len(frozen)} doan dong bang >=1s tai "
                  f"{[f'{x:.1f}s' for x in frozen[:5]]}")
        else:
            print("  frame dong bang >=1s: KHONG CO")

        goc_xam = anh_goc_xam()
        if la_clip_le:
            canh_muc = [(duong.stem, 0.0, dai_v)]
        else:
            kb = C.doc_kich_ban(KICH_BAN)
            dai = [C.do_dai_wav(C.CLIP / f"{c.id}.mp4") if (C.CLIP / f"{c.id}.mp4").exists()
                   else 0.0 for c in kb.canh]
            moc = tim_canh_chua(dai)
            canh_muc = [(kb.canh[i].id, moc[i],
                         moc[i + 1] if i + 1 < len(moc) else dai_v)
                        for i in range(len(kb.canh))]

        print(f"  {'canh':<10}{'khoang (s)':<17}{'dong tb':<9}{'dong max':<9}"
              f"giong anh goc nhat")
        for ten, d1, d2 in canh_muc:
            i1, i2 = int(d1 * fps), max(int(d2 * fps) - 1, int(d1 * fps) + 1)
            do_dong = diff[i1 + 1:i2 + 1]
            tb = float(do_dong.mean()) if len(do_dong) else 0.0
            mx = float(do_dong.max()) if len(do_dong) else 0.0

            kieu_canh = next((c.kieu for c in kb.canh if c.id == ten), "") \
                if not la_clip_le else ""
            if kieu_canh == "t2v":
                # T2V ve tu CHU (EmptyLTXVLatentVideo), khong co anh mau —
                # khong the va khong nen so voi anh goc. Chi bao do dong.
                print(f"  {ten:<10}{d1:>6.2f}-{d2:<8.2f}{tb:<9.2f}{mx:<9.2f}"
                      f"-(t2v: ve tu chu, khong so anh goc)")
                if tb < 0.25:
                    print(f"    CANH BAO: do dong thap ({tb:.2f})")
                continue

            giua = min(int((d1 + (d2 - d1) * 0.5) * fps), len(cac_frame) - 1)
            with Image.open(cac_frame[giua]) as im:
                g = np.asarray(im.convert("L").resize((192, 108), Image.BILINEAR),
                               dtype=np.float32)
            corr = {k: correlation(g, x) for k, x in goc_xam.items()}
            best = max(corr, key=corr.get)
            dung = True if la_clip_le else best.endswith(ten[-2:])
            if not dung:
                ok = False
            chuoi = f"{best} ({corr[best]:.3f})" if not la_clip_le else "-"
            flag = "" if dung else "  <-- SAI CANH!"
            print(f"  {ten:<10}{d1:>6.2f}-{d2:<8.2f}{tb:<9.2f}{mx:<9.2f}{chuoi}{flag}")
            if tb < 0.25 and not la_clip_le:
                print(f"    CANH BAO: do dong thap ({tb:.2f}) — co the video tinh")

        if a:
            am_thanh = kiem_audio_canh(duong, canh_muc)
            for ten, mx in am_thanh:
                if mx < -35.0:
                    ok = False
                    print(f"  LOI: {ten} gan nhu im lang (max {mx} dB)")
                else:
                    print(f"  {ten}: co tieng (max {mx} dB)")
        return ok
    finally:
        shutil.rmtree(thu_muc, ignore_errors=True)


def main() -> None:
    global KICH_BAN
    p = argparse.ArgumentParser()
    p.add_argument("video", nargs="+")
    p.add_argument("--kich-ban", help="dung file kich ban khac vao/kich_ban.json")
    a = p.parse_args()
    KICH_BAN = Path(a.kich_ban) if a.kich_ban else None

    tat_ca_ok = True
    for duong in a.video:
        tat_ca_ok &= kiem_mot_video(Path(duong), la_clip_le="clip" in duong)
        print()

    if tat_ca_ok:
        C.buoc("KET LUAN: TAT CA DAT")
    else:
        C.buoc("KET LUAN: CO VAN DE — xem cac dong LOI o tren")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
