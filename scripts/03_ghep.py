"""Buoc 3/3 -- ra/clip/*.mp4 + phu de  ->  ra/video_cuoi.mp4

Noi cac clip theo dung thu tu trong kich ban, sinh phu de tu chinh loi thoai
(moc thoi gian lay tu do dai that cua tung clip, khong doan), roi in phu de
len hinh.

  python scripts/03_ghep.py
  python scripts/03_ghep.py --phu-de mem   # phu de roi (bat/tat duoc), khong in len hinh
  python scripts/03_ghep.py --phu-de khong
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chung as C


def gio_srt(giay: float) -> str:
    ms = int(round(giay * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def cat_dong(text: str, moi_dong: int = 42) -> str:
    """Be loi thoai thanh toi da 2 dong cho de doc."""
    tu, dong, hien = text.split(), [], ""
    for t in tu:
        if len(hien) + len(t) + 1 > moi_dong and hien:
            dong.append(hien)
            hien = t
        else:
            hien = f"{hien} {t}".strip()
    if hien:
        dong.append(hien)
    if len(dong) <= 2:
        return "\n".join(dong)
    giua = (len(dong) + 1) // 2
    return "\n".join([" ".join(dong[:giua]), " ".join(dong[giua:])])


def lam_srt(kb, clip: list, duong: Path, chong: float = 0.0) -> int:
    """Sinh phu de. `chong` = so giay hai clip chong len nhau khi chuyen canh;
    moi lan chuyen lam toan bo phan sau tien len dung bay nhieu giay."""
    khoi, moc, n = [], 0.0, 0
    for canh, dai in clip:
        if canh.co_thoai:
            n += 1
            # Ket thuc TRUOC khi canh sau bat dau. Khong tru phan chong thi hai
            # dong phu de cung hien trong luc chuyen canh -- da dinh: chong
            # 0,34s giua canh 1 va 2, man hinh ra hai khoi chu long nhau.
            # dai da bao gom phan dem cuoi; phu de nen tat khi loi het chu
            # khong keo qua phan dem im lang.
            het = moc + dai - chong - 0.12
            khoi.append(f"{n}\n{gio_srt(moc + 0.08)} --> {gio_srt(max(moc + 0.5, het))}\n"
                        f"{cat_dong(canh.thoai.strip())}\n")
        moc += dai - chong
    duong.write_text("\n".join(khoi), encoding="utf-8")
    return n


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--phu-de", choices=["in", "mem", "khong"], default=None,
                   help="in = in len hinh (mac dinh) | mem = phu de roi | khong")
    p.add_argument("--kich-ban", help="dung file kich ban khac vao/kich_ban.json")
    p.add_argument("--ra", default=None)
    p.add_argument("--cham", type=float, default=1.0,
                   help="he so lam cham. 1.15 = cham hon 15%%. Lam cham CA hinh "
                        "lan tieng cung mot he so nen mieng van khop.")
    p.add_argument("--chuyen-canh", type=float, default=0.5,
                   help="giay cho hieu ung chuyen canh (0 = cat thang)")
    p.add_argument("--kieu-chuyen", default="fade",
                   help="fade · fadeblack · dissolve · wipeleft · slideleft · smoothleft · circleopen")
    p.add_argument("--do")
    a = p.parse_args()

    kb = C.doc_kich_ban(Path(a.kich_ban) if getattr(a, "kich_ban", None) else None)
    kieu = a.phu_de or ("in" if kb.phu_de else "khong")
    ra = Path(a.ra) if a.ra else C.VIDEO_CUOI
    if not ra.is_absolute():
        ra = C.GOC / ra          # --ra co the la duong dan tuong doi

    thieu = [c.id for c in kb.canh if not c.duong_clip.exists()]
    if thieu:
        C.loi("Chua co clip cho: " + ", ".join(thieu) +
              "\nChay buoc 2 truoc: python scripts/02_hoat_hinh.py")

    t0 = time.time()

    # LAM CHAM: keo dan CA hinh (setpts) lan tieng (atempo) cung mot he so.
    # Chi lam cham tieng thoi thi mieng se khong con khop nua -- day la ly do
    # phai dung cham ca hai chu khong dung mot minh atempo.
    # atempo giu nguyen CAO DO giong (khong bi tram di nhu khi doi sample rate).
    if abs(a.cham - 1.0) > 0.01:
        C.buoc(f"Lam cham {a.cham:.2f}x (ca hinh lan tieng, mieng van khop)")
        for c in kb.canh:
            if not c.duong_clip.exists():
                continue
            tam = C.LOGS / f"_cham_{c.id}.mp4"
            r = subprocess.run(
                [C.FFMPEG, "-y", "-v", "error", "-i", str(c.duong_clip),
                 "-filter_complex",
                 f"[0:v]setpts={a.cham}*PTS[v];[0:a]atempo={1/a.cham:.6f}[a]",
                 "-map", "[v]", "-map", "[a]",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(tam)],
                capture_output=True, text=True)
            if r.returncode:
                C.loi(f"ffmpeg loi khi lam cham {c.id}:\n{r.stderr[-800:]}")
            tam.replace(c.duong_clip)
            C.noi(f"  {c.id}: {C.do_dai_wav(c.duong_clip):.2f}s")

    clip = [(c, C.do_dai_wav(c.duong_clip)) for c in kb.canh]
    tong = sum(d for _, d in clip)
    C.buoc(f"Noi {len(clip)} clip = {tong:.2f}s  ({tong / 60:.1f} phut)")
    for c, d in clip:
        C.noi(f"  {c.id:<12} {d:6.2f}s  {'co thoai' if c.co_thoai else 'khong thoai'}")

    # Chuyen canh: xfade chong mo hai clip len nhau, nen video NGAN LAI dung
    # bang tong thoi gian chong. Phai tinh lai moc phu de theo do, khong thi
    # tu canh thu hai tro di chu se tre dan.
    gd = max(0.0, a.chuyen_canh) if len(clip) > 1 else 0.0
    if gd > 0:
        ngan_nhat = min(d for _, d in clip)
        if gd > ngan_nhat * 0.4:
            gd = round(ngan_nhat * 0.4, 2)
            C.noi(f"clip ngan nhat {ngan_nhat:.2f}s -> rut chuyen canh xuong {gd}s")

    ds = C.LOGS / "_noi_clip.txt"
    ds.write_text("".join(f"file '{c.duong_clip}'\n" for c, _ in clip), encoding="utf-8")

    srt = C.RA / "phu_de.srt"
    so_dong = lam_srt(kb, clip, srt, gd) if kieu != "khong" else 0
    if so_dong:
        C.noi(f"phu de: {so_dong} khoi -> {srt.relative_to(C.GOC)}")

    if gd > 0:
        # NOI DUOI TRUOC KHI CHONG MO.
        #
        # LTX lap day loi noi den tan khung cuoi (do duoc: chi con 0,01-0,10s
        # im lang o duoi). Chong mo 0,5s se an mat 0,4-0,49s LOI THAT -- nghe
        # ra la "chua doc xong da chuyen canh". Nen truoc khi chong, keo dai
        # moi clip (tru clip cuoi) them dung bang thoi gian chong + 0,15s bien:
        # giu nguyen khung hinh cuoi va noi them im lang. Chuyen canh se an vao
        # phan dem nay thay vi an vao tieng.
        dem = gd + 0.15
        dai_moi = []
        tam_dem = []
        for i, (c, d) in enumerate(clip):
            if i == len(clip) - 1:
                dai_moi.append(d); tam_dem.append(c.duong_clip); continue
            ra_t = C.LOGS / f"_dem_{c.id}.mp4"
            r = subprocess.run(
                [C.FFMPEG, "-y", "-v", "error", "-i", str(c.duong_clip),
                 "-vf", f"tpad=stop_mode=clone:stop_duration={dem}",
                 "-af", f"apad=pad_dur={dem}",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                 "-t", f"{d + dem:.3f}", str(ra_t)], capture_output=True, text=True)
            if r.returncode:
                C.loi(f"ffmpeg loi khi noi duoi {c.id}:\n{r.stderr[-800:]}")
            dai_moi.append(d + dem); tam_dem.append(ra_t)
        C.noi(f"noi them {dem:.2f}s duoi moi clip de chuyen canh khong an vao loi")
        clip = [(c, dai_moi[i]) for i, (c, _) in enumerate(clip)]

        lenh = [C.FFMPEG, "-y"]
        for t in tam_dem:
            lenh += ["-i", str(t)]
        v, aa, moc = "[0:v]", "[0:a]", 0.0
        loc = []
        for i in range(1, len(clip)):
            moc += clip[i - 1][1] - gd
            rv, ra_ = f"[v{i}]", f"[a{i}]"
            loc.append(f"{v}[{i}:v]xfade=transition={a.kieu_chuyen}:"
                       f"duration={gd}:offset={moc:.3f}{rv}")
            loc.append(f"{aa}[{i}:a]acrossfade=d={gd}:c1=tri:c2=tri{ra_}")
            v, aa = rv, ra_
        C.noi(f"chuyen canh: {a.kieu_chuyen} {gd}s x {len(clip) - 1} lan")
    else:
        lenh = [C.FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(ds)]
        loc, v, aa = [], None, None
    if gd > 0:
        kieu_chu = ("FontName=DejaVu Sans,FontSize=19,PrimaryColour=&H00FFFFFF,"
                    "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,"
                    "MarginV=28,Alignment=2")
        if kieu == "in" and so_dong:
            loc.append(f"{v}subtitles={srt}:force_style='{kieu_chu}'[vr]")
            v = "[vr]"
        lenh += ["-filter_complex", ";".join(loc), "-map", v, "-map", aa,
                 "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", str(ra)]
        C.buoc(f"ffmpeg dang ghep (phu de: {kieu}, chuyen canh: {a.kieu_chuyen})")
        r = subprocess.run(lenh, capture_output=True, text=True)
        ds.unlink(missing_ok=True)
        for t in tam_dem:
            if t.parent == C.LOGS:
                t.unlink(missing_ok=True)
        if r.returncode:
            C.loi(f"ffmpeg loi:\n{r.stderr[-1500:]}")
        dai = C.do_dai_wav(ra); mb = ra.stat().st_size / 1048576
        C.buoc(f"XONG -> {ra.relative_to(C.GOC)}  {dai:.2f}s  {mb:.1f} MB  "
               f"(ghep mat {time.time() - t0:.1f}s)")
        if a.do:
            Path(a.do).write_text(json.dumps(
                {"buoc": "ghep", "so_clip": len(clip), "giay_video": round(dai, 2),
                 "mb": round(mb, 1), "phu_de": kieu, "khoi_phu_de": so_dong,
                 "chuyen_canh": a.kieu_chuyen, "giay_chuyen": gd},
                ensure_ascii=False, indent=2), encoding="utf-8")
        return

    if kieu == "mem" and so_dong:
        lenh += ["-i", str(srt), "-c", "copy", "-c:s", "mov_text",
                 "-metadata:s:s:0", "language=eng"]
    elif kieu == "in" and so_dong:
        # In phu de len hinh. Vien den + nen mo de doc duoc tren moi nen anh.
        kieu_chu = ("FontName=DejaVu Sans,FontSize=19,PrimaryColour=&H00FFFFFF,"
                    "OutlineColour=&H00000000,BorderStyle=1,Outline=2,Shadow=1,"
                    "MarginV=28,Alignment=2")
        lenh += ["-vf", f"subtitles={srt}:force_style='{kieu_chu}'",
                 "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                 "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k"]
    else:
        lenh += ["-c", "copy"]
    lenh += [str(ra)]

    C.buoc(f"ffmpeg dang ghep (phu de: {kieu})")
    r = subprocess.run(lenh, capture_output=True, text=True)
    ds.unlink(missing_ok=True)
    if r.returncode:
        C.loi(f"ffmpeg loi:\n{r.stderr[-1500:]}")

    dai = C.do_dai_wav(ra)
    mb = ra.stat().st_size / 1048576
    C.buoc(f"XONG -> {ra.relative_to(C.GOC)}  {dai:.2f}s  {mb:.1f} MB  "
           f"(ghep mat {time.time() - t0:.1f}s)")

    if a.do:
        Path(a.do).write_text(json.dumps(
            {"buoc": "ghep", "so_clip": len(clip), "giay_video": round(dai, 2),
             "mb": round(mb, 1), "phu_de": kieu, "khoi_phu_de": so_dong},
            ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
