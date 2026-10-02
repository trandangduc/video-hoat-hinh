"""XUONG VIDEO — nguoi dung tu viet tung canh, tao tung canh, duyet, roi MERGE.

Moi du an mot thu muc ra/xuong/<id>/:
  du_an.json          cai dat chung + danh sach canh. Moi canh co "id" rieng nen doi thu tu
                      khong lam mat ban da ve.
  tieng/<cid>.wav     loi doc cua canh (Chatterbox, tieng Anh)   + <cid>.json {dau, giay}
  clip/<cid>.brd      hinh cua canh (LTX-2.5)                     + <cid>.json {dau, khung, giay, ...}
  clip/<cid>.loi      loi cua lan tao gan nhat (xoa khi tao lai thanh cong)
  bd_<ma>.brd     ket qua merge (ma hoa)

Luat do dai (nguoi dung chot 10/09/2026): canh CO loi doc thi tu dai bang giong + DUOI giay,
khong vuot muc toi da — dai qua thi bao tach canh. Canh KHONG loi doc thi theo so giay nguoi chon.

Anh mau, moi canh tu chon: "khong" · "mo_ta" (ghep cau ta nhan vat vao prompt, canh van tu do)
· "khung_dau" (anh lam khung mo dau — i2v, giong hon nhung mo dau y het anh).

  python cong_cu/xuong.py canh  ra/xuong/<id>/du_an.json <cid>
  python cong_cu/xuong.py merge ra/xuong/<id>/du_an.json
"""
from __future__ import annotations

import hashlib
import video_bao_mat as VB
import json
import shutil
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
sys.path.insert(0, str(GOC / "scripts"))
import chung as C                # noqa: E402
import du_an as DA               # noqa: E402
import lam_video_collage as LV   # noqa: E402

XUONG = GOC / "ra" / "xuong"
CAU_HINH = GOC / "logs" / "xuong_cau_hinh.json"      # so do tu cong_cu do_max -> gioi han that
DUOI = 0.5                                            # giay de lai sau tieng cuoi cua loi doc
W, H, FPS = LV.W, LV.H, LV.FPS
KIEU_ANH = ("khong", "mo_ta", "khung_dau", "tham_chieu")
# tham_chieu: IC-LoRA Ingredients + bang tham chieu dung tu anh mau (thu 11/09: 3/3 canh giu dung nhan vat,
# ~146 s / 121 khung, ra 1536x896). Model huan luyen o 121 khung (5 giay) nen tam gioi han 10 giay.
MAC_DINH = {"giay_toi_da": 10.0, "giay_toi_da_khung_dau": 10.0, "giay_toi_da_tham_chieu": 10.0,
            "s_moi_khung": 2.45, "s_moi_khung_khung_dau": 3.9, "s_moi_khung_tham_chieu": 1.2}
BANG = "bang_tham_chieu.png"


def xoa_du_an(d: Path) -> None:
    """Xoa du lieu tren dia, ke ca dau ra ComfyUI con sot sau lan ve loi/huy."""
    for folder in (DA.COMFY / "output" / "xuong", DA.COMFY / "input"):
        for p in folder.glob(f"{d.name}_*"):
            if p.is_file() or p.is_symlink():
                p.unlink()
    shutil.rmtree(d)


def cau_hinh() -> dict:
    ch = dict(MAC_DINH)
    if CAU_HINH.exists():
        try:
            ch.update(json.loads(CAU_HINH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return ch


def doc_du_an(duong: Path) -> dict:
    return json.loads(duong.read_text(encoding="utf-8"))


def _json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _dau_file(p: Path | None) -> str:
    if not p or not p.exists():
        return ""
    s = p.stat()
    return f"{p.name}:{s.st_size}:{int(s.st_mtime)}"


def _sha(x) -> str:
    return hashlib.sha1(json.dumps(x, ensure_ascii=False).encode()).hexdigest()[:12]


def tim_canh(da: dict, cid: str) -> dict:
    for c in da.get("canh") or []:
        if c.get("id") == cid:
            return c
    raise RuntimeError(f"Khong co canh '{cid}'")


# --------------------------------------------------------------------- dau van tay

def dung_tham_chieu(c: dict, da: dict) -> bool:
    return c.get("anh") == "tham_chieu" and bool(da.get("anh_mau"))


def ta_bang(da: dict) -> str:
    """Phan 'Reference sheet:' — model card dan phai ta TUNG O cua bang (cong_cu/tach_nen.dung_bang)."""
    nv = (da.get("mo_ta_anh") or "").strip().rstrip(".") or "the main character"
    return (f"**Left (Character):** A front-facing close-up of the character's face and headwear: {nv}. "
            f"**Right (Character):** A full-body turnaround of the same character, front view and mirrored front view.")


def prompt_day_du(c: dict, da: dict) -> str:
    than = (c.get("prompt") or "").strip()
    pc = (da.get("phong_cach") or "").strip()
    if dung_tham_chieu(c, da):
        return f"Reference sheet: {ta_bang(da)} Generated video: {pc.rstrip('.') + '. ' if pc else ''}{than}"
    if c.get("anh") in ("mo_ta", "khung_dau") and da.get("anh_mau") and (da.get("mo_ta_anh") or "").strip():
        than = f"{da['mo_ta_anh'].strip().rstrip('.')}. {than}"
    return f"{pc}: {than}" if pc else than


def dam_bao_bang(da: dict, D: Path) -> Path:
    """Bang tham chieu cua du an; dung lai khi chua co hoac cu hon anh mau (server cung dung ngay luc tai anh)."""
    b, anh = D / BANG, D / da["anh_mau"]
    if not b.exists() or b.stat().st_mtime < anh.stat().st_mtime:
        import tach_nen as TN
        TN.dung_bang_tu_anh(anh, b)
    return b


def che_do(da: dict) -> str:
    """Che do ve cua du an (DA.CHE_DO). KHONG nam trong dau van tay clip: doi che do khong lam canh da ve
    thanh 'cu' — ban nhap nhanh van merge duoc; 'Tao het' moi ve lai cac canh khac che do."""
    return da.get("che_do") if da.get("che_do") in DA.CHE_DO else "chuan"


def anh_khung(c: dict, da: dict, D: Path) -> Path | None:
    if c.get("anh") == "khung_dau" and da.get("anh_mau") and (D / da["anh_mau"]).exists():
        return D / da["anh_mau"]
    return None


def dau_tieng(c: dict, da: dict, D: Path) -> str:
    g = da.get("giong") or {}
    mau = D / g["mau"] if g.get("mau") else None
    return _sha([(c.get("loi_doc") or "").strip(), _dau_file(mau), g.get("cam_xuc", "binh_thuong")])


def hat_giong(c: dict, da: dict) -> int:
    return int(da.get("seed", 1234)) + int(hashlib.sha1(c["id"].encode()).hexdigest()[:6], 16) % 100000


def dau_clip(c: dict, da: dict, D: Path, k: int) -> str:
    x = [prompt_day_du(c, da), k, _dau_file(anh_khung(c, da, D)), hat_giong(c, da)]
    if dung_tham_chieu(c, da):             # chi them khi dung bang -> dau cua cac canh cu khong doi
        x += ["tham_chieu", _dau_file(D / BANG)]
    return _sha(x)


def giay_canh(c: dict, giay_tieng: float | None, ch: dict) -> tuple[float | None, str]:
    toi_da = {"khung_dau": ch["giay_toi_da_khung_dau"],
              "tham_chieu": ch.get("giay_toi_da_tham_chieu", ch["giay_toi_da"])}.get(c.get("anh"), ch["giay_toi_da"])
    if (c.get("loi_doc") or "").strip():
        if giay_tieng is None:
            return None, ""
        can = round(giay_tieng + DUOI, 2)
        if can > toi_da:
            return None, (f"Lời đọc dài {giay_tieng:.1f} giây, vượt tối đa {toi_da:g} giây của một cảnh — "
                          f"tách thành 2 cảnh.")
        return max(1.0, can), ""
    return round(min(toi_da, max(1.0, float(c.get("giay") or 3))), 2), ""


def trang_thai_canh(c: dict, da: dict, D: Path, ch: dict | None = None) -> dict:
    """xong | cu (da sua sau lan tao truoc) | chua_tao | loi — chua tinh viec dang xep hang."""
    ch = ch or cau_hinh()
    cid = c["id"]
    co_loi = bool((c.get("loi_doc") or "").strip())
    tj = _json(D / "tieng" / f"{cid}.json")
    tieng_ok = co_loi and (D / "tieng" / f"{cid}.wav").exists() and tj.get("dau") == dau_tieng(c, da, D)
    giay, loi_giay = giay_canh(c, tj.get("giay") if tieng_ok else None, ch)
    mp4, cj = D / "clip" / f"{cid}.brd", _json(D / "clip" / f"{cid}.json")
    clip_ok = bool(giay) and mp4.exists() and cj.get("dau") == dau_clip(c, da, D, DA.so_khung(giay))
    loi_file = D / "clip" / f"{cid}.loi"
    if loi_giay:
        tt = "loi"
    elif clip_ok and (not co_loi or tieng_ok):
        tt = "xong"
    elif loi_file.exists():
        tt = "loi"
    elif mp4.exists():
        tt = "cu"
    else:
        tt = "chua_tao"
    loi = loi_giay or (loi_file.read_text(encoding="utf-8") if tt == "loi" and loi_file.exists() else "")
    cd_clip = cj.get("che_do", "chuan") if clip_ok else None
    return {"trang_thai": tt, "giay": giay, "giay_tieng": tj.get("giay") if tieng_ok else None,
            "co_clip": mp4.exists(), "co_tieng": tieng_ok, "loi": loi,
            "giay_render": cj.get("giay_render") if clip_ok else None,
            # canh bang tham chieu luon ve bang distilled + LoRA, khong theo nut Chuan/Nhanh
            "che_do": cd_clip, "khac_che_do": bool(cd_clip and cd_clip != "tham_chieu" and cd_clip != che_do(da))}


def _ban_clip(D: Path, cid: str) -> list:
    """Dau cua BAN clip dang nam tren dia = dau van tay + che do ve. Ve lai cung prompt o che do khac thi
    dau van tay giu nguyen (co y — xem che_do) nhung HINH da khac -> video da merge phai bao 'cu'.
    'chuan' khong ghi them de dau_merge cua du an lam truoc khi co che do van khop."""
    cj = _json(D / "clip" / f"{cid}.json")
    cd = cj.get("che_do", "chuan")
    return [cj.get("dau")] + ([cd] if cd != "chuan" else [])


def dau_ban_ghep(da: dict, D: Path, ch: dict | None = None) -> str:
    """Dau van tay cua bo canh hien tai: video da merge con khop voi cac canh khong."""
    ch = ch or cau_hinh()
    return _sha([[c["id"], trang_thai_canh(c, da, D, ch)["giay"], *_ban_clip(D, c["id"])]
                 for c in da.get("canh") or []])


# ------------------------------------------------------------------------ tien do

def _bao(D: Path, buoc: str, cid: str, ghi: str, t0: float, pt: float | None = None) -> None:
    (D / "tien_do.json").write_text(json.dumps(
        {"buoc": buoc, "canh": cid, "ghi": ghi, "bat_dau": t0, "luc": time.time(), "phan_tram": pt}, ensure_ascii=False),
        encoding="utf-8")
    print(f"[{time.strftime('%H:%M:%S')}] {buoc} {cid}  {ghi}", flush=True)


def _bao_canh(D: Path, cid: str, pha: str, pt: float, t0: float, con_lai: float | None = None) -> None:
    """Tien do RIENG tung canh (tien_do/<cid>.json): 2 GPU ve song song 2 canh cung du an thi tien_do.json
    chung bi de nhau."""
    tm = D / "tien_do"
    tm.mkdir(exist_ok=True)
    tam = tm / f".{cid}.tmp"
    tam.write_text(json.dumps({"pha": pha, "phan_tram": round(min(100.0, pt), 1), "bat_dau": t0,
                               "con_lai": round(con_lai) if con_lai else None, "luc": time.time()},
                              ensure_ascii=False), encoding="utf-8")
    tam.replace(tm / f"{cid}.json")


# ------------------------------------------------------------------------ tao canh

def tao_canh(duong: Path, cid: str) -> dict:
    D = duong.parent
    da, ch = doc_du_an(duong), cau_hinh()
    c = tim_canh(da, cid)
    loi_file = D / "clip" / f"{cid}.loi"
    t0 = time.time()
    try:
        if not (c.get("prompt") or "").strip():
            raise RuntimeError("Cảnh chưa có prompt hình.")
        giay_tieng = None
        if (c.get("loi_doc") or "").strip():
            wav, tj = D / "tieng" / f"{cid}.wav", D / "tieng" / f"{cid}.json"
            d = dau_tieng(c, da, D)
            if wav.exists() and _json(tj).get("dau") == d:
                giay_tieng = _json(tj)["giay"]
            else:
                _bao(D, "giong", cid, "đang đọc lời", t0)
                _bao_canh(D, cid, "Đang đọc lời", 2, t0)
                import giong_doc as GD
                g = da.get("giong") or {}
                kq = GD.doc(c["loi_doc"], wav, D / g["mau"] if g.get("mau") else None, g.get("cam_xuc", "binh_thuong"))
                giay_tieng = kq["giay"]
                tj.write_text(json.dumps({"dau": d, "giay": giay_tieng}, ensure_ascii=False), encoding="utf-8")
        giay, loi = giay_canh(c, giay_tieng, ch)
        if loi:
            raise RuntimeError(loi)
        k = DA.so_khung(giay)
        ra, the = D / "clip" / f"{cid}.brd", D / "clip" / f"{cid}.json"
        tc = dung_tham_chieu(c, da)
        if tc:                                 # truoc dau_clip: dau van tay tinh ca file bang
            _bao(D, "ve", cid, "chuẩn bị bảng tham chiếu nhân vật", t0)
            _bao_canh(D, cid, "Chuẩn bị bảng tham chiếu nhân vật", 4, t0)
            dam_bao_bang(da, D)
        d, cd = dau_clip(c, da, D, k), ("tham_chieu" if tc else che_do(da))
        if ra.exists() and _json(the).get("dau") == d and _json(the).get("che_do", "chuan") == cd:
            giu = True
        else:
            giu = False
            khung = anh_khung(c, da, D)
            t = time.time()
            nen = 6.0 if (c.get("loi_doc") or "").strip() else 0.0    # 0-6% la doc loi / chuan bi

            def cb(pha: str, pt: float, con_lai: float | None) -> None:
                _bao_canh(D, cid, pha, nen + (100 - nen) * pt / 100, t0, con_lai)
            with VB.workspace() as work:
                plain = work / "render.mp4"
                if tc:
                    s = ch.get("s_moi_khung_tham_chieu", 1.2)
                    _bao(D, "ve", cid, f"{giay:g}s = {k} khung · giữ nhân vật (bảng tham chiếu) · ước tính ~{max(1, round(k * s / 60))} phút", t0)
                    DA.ve_tham_chieu(prompt_day_du(c, da), k, hat_giong(c, da), D / BANG, plain, f"xuong/{D.name}_{cid}", tien_do=cb)
                else:
                    s = ch["s_moi_khung_khung_dau" if khung else "s_moi_khung"] * (ch.get("he_so_nhanh", 1.0) if cd == "nhanh" else 1.0)
                    _bao(D, "ve", cid, f"{giay:g}s = {k} khung · {'nhanh' if cd == 'nhanh' else 'chuẩn'} · ước tính ~{max(1, round(k * s / 60))} phút", t0)
                    DA.ve_mot_clip(prompt_day_du(c, da), k, hat_giong(c, da), khung, plain, f"xuong/{D.name}_{cid}", cd, tien_do=cb)
                VB.seal(plain, ra)
            the.write_text(json.dumps({"dau": d, "khung": k, "giay": giay, "prompt": prompt_day_du(c, da),
                                       "khung_dau": bool(khung), "tham_chieu": tc, "che_do": cd,
                                       "giay_render": round(time.time() - t, 1)},
                                      ensure_ascii=False, indent=1), encoding="utf-8")
        loi_file.unlink(missing_ok=True)
        (D / "tien_do" / f"{cid}.json").unlink(missing_ok=True)
        _bao(D, "xong_canh", cid, "giữ bản cũ" if giu else f"xong sau {time.time() - t0:.0f}s", t0)
        return {"giay": giay, "giu": giu}
    except BaseException as e:
        (D / "tien_do" / f"{cid}.json").unlink(missing_ok=True)
        if not isinstance(e, KeyboardInterrupt):
            loi_file.parent.mkdir(parents=True, exist_ok=True)
            loi_file.write_text(str(e)[:800], encoding="utf-8")
        raise


# ---------------------------------------------------------------------------- merge

def merge(duong: Path) -> Path:
    with VB.workspace() as tm:
        return _merge(duong, tm)


def _merge(duong: Path, tm: Path) -> Path:
    D = duong.parent
    da, ch = doc_du_an(duong), cau_hinh()
    canh = da.get("canh") or []
    if not canh:
        raise RuntimeError("Dự án chưa có cảnh nào.")
    tt = [trang_thai_canh(c, da, D, ch) for c in canh]
    chua = [str(i + 1) for i, s in enumerate(tt) if s["trang_thai"] != "xong"]
    if chua:
        raise RuntimeError(f"Chưa merge được — cảnh chưa tạo xong hoặc đã sửa mà chưa tạo lại: {', '.join(chua)}")
    t0 = time.time()
    doan, moc, t = [], [], 0.0
    for i, (c, s) in enumerate(zip(canh, tt)):
        _bao(D, "merge", c["id"], f"ghép cảnh {i + 1}/{len(canh)}", t0, 80 * i / len(canh))
        nguon, giay = tm / "source.mp4", s["giay"]
        VB.unpack(D / "clip" / f"{c['id']}.brd", nguon)
        cat = LV.tu_cat(nguon, giay)
        seg = tm / f"{i:03d}.mp4"
        LV.chay([LV.FF, "-v", "error", "-y", "-i", str(nguon), "-an",
                 "-vf", f"trim=0:{giay},setpts=PTS-STARTPTS,fps={FPS},{cat}scale={W}:{H},setsar=1",
                 "-t", str(giay), "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(seg)])
        nguon.unlink()
        doan.append(seg)
        moc.append((t, D / "tieng" / f"{c['id']}.wav" if s["co_tieng"] else None))
        t += LV.do_dai(seg)          # do dai THAT cua doan (lam tron khung) -> loi doc khong troi dan
    ds = tm / "ds.txt"
    ds.write_text("".join(f"file '{p}'\n" for p in doan))
    ghep = tm / "ghep.mp4"
    LV.chay([LV.FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(ds), "-c", "copy", str(ghep)])
    tong = LV.do_dai(ghep)

    _bao(D, "merge", "", "trộn lời đọc, nhạc và xuất video", t0, 85)
    vao, loc, nhanh, so = ["-i", str(ghep)], [], [], 1
    for bat_dau, wav in moc:
        if wav:
            vao += ["-i", str(wav)]
            loc.append(f"[{so}:a]aformat=sample_rates=48000:channel_layouts=stereo,adelay={int(bat_dau * 1000)}:all=1[g{so}]")
            nhanh.append(f"[g{so}]")
            so += 1
    nhac = D / da["nhac"] if da.get("nhac") else None
    if nhac and nhac.exists():
        # Co loi doc thi nhac nho han han de khong de len giong
        vao += ["-stream_loop", "-1", "-i", str(nhac)]
        loc.append(f"[{so}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                   f"volume={0.18 if nhanh else 0.8},atrim=0:{tong:.3f}[nh]")
        nhanh.append("[nh]")
        so += 1
    if not nhanh:
        vao += ["-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo:d={tong:.3f}"]
        loc.append(f"[{so}:a]anull[im]")
        nhanh.append("[im]")
    loc.append(f"{''.join(nhanh)}amix=inputs={len(nhanh)}:normalize=0:duration=longest,"
               f"atrim=0:{tong:.3f},afade=t=out:st={max(0, tong - 0.6):.3f}:d=0.6[a]")
    hieu_ung = "noise=alls=5:allf=t,vignette=PI/5," if da.get("hieu_ung_phim", True) else ""
    loc.append(f"[0:v]{hieu_ung}fade=t=in:d=0.3,fade=t=out:st={max(0, tong - 0.5):.3f}:d=0.5[v]")
    ra = tm / "video.mp4"
    LV.chay([LV.FF, "-v", "error", "-y"] + vao +
            ["-filter_complex", ";".join(loc), "-map", "[v]", "-map", "[a]", "-t", f"{tong:.3f}",
             "-c:v", "libx264", "-crf", "19", "-preset", "slow", "-pix_fmt", "yuv420p",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(ra)])
    giay_video = round(LV.do_dai(ra), 2)
    ra = VB.seal(ra, VB.merged_path(D))
    da = doc_du_an(duong)       # doc lai: nguoi dung co the da sua trong luc merge
    da.update(video=ra.name, giay_video=giay_video, merge_luc=time.strftime("%Y-%m-%d %H:%M:%S"),
              dau_merge=_sha([[c["id"], s["giay"], *_ban_clip(D, c["id"])] for c, s in zip(canh, tt)]))
    duong.write_text(json.dumps(da, ensure_ascii=False, indent=2), encoding="utf-8")
    _bao(D, "xong_merge", "", f"video {da['giay_video']}s", t0)
    return ra


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[1] not in ("canh", "merge"):
        sys.exit(__doc__)
    duong = Path(sys.argv[2]).resolve()
    if sys.argv[1] == "canh":
        print(json.dumps(tao_canh(duong, sys.argv[3]), ensure_ascii=False))
    else:
        print(merge(duong))


if __name__ == "__main__":
    main()
