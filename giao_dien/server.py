"""Giao dien web cho pipeline.

    python giao_dien/server.py                # chi may nay xem duoc
    CHIA=1 python giao_dien/server.py         # mo ra mang LAN cho nguoi khac

Chi lam nam viec: chon/sua kich ban, nhan file vao, bam chay tung buoc, xem
log + ket qua, va tai video ve. Moi tinh toan van do 3 script trong scripts/
lam -- giao dien chi goi chung nhu goi tu dong lenh, khong nhan ban logic.

Viec chay NEN va roi han khoi server (xem giao_dien/viec.py): bam chay xong
dong trinh duyet, tat ca server cung duoc, mai mo lai van thay tien do va
video da xong.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import (FileResponse, HTMLResponse, JSONResponse,
                               PlainTextResponse, RedirectResponse, StreamingResponse)

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import chung as C
from viec import ViecNen

TINH = Path(__file__).resolve().parent / "tinh"
app = FastAPI(title="Video hoat hinh")

VIEC = ViecNen(C.LOGS / "viec", C.GOC)
PY_VENV = str(C.GOC / ".venv" / "bin" / "python")

# Kich ban dang mo. Nho qua ca lan khoi dong lai nen cat ra file.
GHI_NHO = C.LOGS / "kich_ban_dang_dung.txt"


# ------------------------------------------------------------- kich ban

def duong_kich_ban() -> Path:
    if GHI_NHO.exists():
        p = Path(GHI_NHO.read_text(encoding="utf-8").strip())
        if not p.is_absolute():
            p = C.GOC / p
        if p.exists():
            return p
    return C.KICH_BAN


def dat_kich_ban(ten: str) -> Path:
    p = (C.VAO / Path(ten).name).resolve()
    if not str(p).startswith(str(C.VAO.resolve())) or not p.exists():
        raise HTTPException(404, f"Khong thay kich ban '{ten}'")
    GHI_NHO.write_text(str(p.relative_to(C.GOC)), encoding="utf-8")
    return p


def cac_kich_ban() -> list[dict]:
    ra = []
    for p in sorted(C.VAO.glob("kich_ban*.json")):
        if ".truoc_" in p.name:          # ban sao luu tu dong
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            ra.append({"ten": p.name, "nhan": d.get("ten_video", p.stem),
                       "so_canh": len(d.get("canh", [])),
                       "kieu": (d.get("cau_hinh") or {}).get("kieu_mac_dinh", "")})
        except Exception:
            continue
    return ra


# --------------------------------------------------------------- trang thai

def anh_trang_thai() -> dict:
    duong = duong_kich_ban()
    try:
        kb = C.doc_kich_ban(duong)
    except SystemExit:
        return {"loi": f"Khong doc duoc {duong.name}"}

    canh = []
    for c in kb.canh:
        canh.append({
            "id": c.id, "anh": c.anh, "thoai": c.thoai,
            "cam_xuc": c.cam_xuc, "ghi_chu": c.ghi_chu, "kieu": c.kieu,
            "co_thoai": c.co_thoai,
            "co_anh": c.duong_anh.exists(),
            "co_tieng": c.duong_wav.exists(),
            "co_clip": c.duong_clip.exists(),
            "giay_tieng": round(C.do_dai_wav(c.duong_wav), 2) if c.duong_wav.exists() else None,
            "giay_clip": round(C.do_dai_wav(c.duong_clip), 2) if c.duong_clip.exists() else None,
        })

    cuoi = duong_video_cuoi()
    return {
        "ten_video": kb.ten_video,
        "kich_ban_dang_dung": duong.name,
        "cac_kich_ban": cac_kich_ban(),
        "cau_hinh": {"fps": kb.fps, "rong": kb.rong, "cao": kb.cao,
                     "giay_canh_khong_thoai": kb.giay_canh_khong_thoai,
                     "phu_de": kb.phu_de, "kieu_mac_dinh": kb.kieu_mac_dinh,
                     "phong_cach_t2v": kb.phong_cach_t2v},
        "kieu": ["ken_burns", "i2v", "s2v", "ltx", "t2v"],
        "canh": canh,
        "cam_xuc": list(C.CAM_XUC),
        "van_de": C.kiem_kich_ban(kb),
        "co_giong_mau": C.GIONG_MAU.exists(),
        "video_cuoi": cuoi.exists(),
        "ten_video_cuoi": cuoi.name if cuoi.exists() else None,
        "mb_video_cuoi": round(cuoi.stat().st_size / 1048576, 1) if cuoi.exists() else None,
        "giay_video_cuoi": round(C.do_dai_wav(cuoi), 2) if cuoi.exists() else None,
    }


def duong_video_cuoi() -> Path:
    """Video cuoi cua kich ban dang mo.

    03_ghep.py ghi ra ra/video_cuoi.mp4 tru khi duoc dua --ra. Voi kich ban
    phu ta dat ten rieng de hai kich ban khong de len nhau.
    """
    ten = duong_kich_ban().stem
    if ten == "kich_ban":
        return C.VIDEO_CUOI
    return C.RA / f"video_{ten.replace('kich_ban_', '')}.mp4"


def may_moc() -> dict:
    d = {"comfy": False, "gpu": []}
    try:
        import urllib.request
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2)
        d["comfy"] = True
    except Exception:
        pass
    try:
        r = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,memory.used,memory.total",
             "--format=csv,noheader,nounits"], capture_output=True, text=True, timeout=8)
        for dong in r.stdout.strip().splitlines():
            i, ten, dung, tong = [x.strip() for x in dong.split(",")]
            d["gpu"].append({"so": int(i), "ten": ten.replace("NVIDIA GeForce ", ""),
                             "dung": int(dung), "tong": int(tong)})
    except Exception:
        pass
    d["gpu_dung"] = C.gpu_dung()
    return d


# ------------------------------------------------------------------- khoa

import bao_mat as AUTH
AUTH.install(app)


# ---------------------------------------------------------------- endpoint

@app.get("/", response_class=HTMLResponse)
def trang_chu() -> str:
    """Trang chinh: Xuong video — tu viet tung canh, tao, duyet, merge."""
    return (TINH / "xuong.html").read_text(encoding="utf-8")


# 11/09/2026 nguoi dung chi dung Xuong video: bo trang "Ke chuyen bang AI" (tao.html) va "Nang cao"
# (index.html) khoi giao dien, duong dan cu chuyen ve trang chinh. File HTML va API cu van giu.
@app.get("/ke-chuyen")
def trang_ke_chuyen() -> RedirectResponse:
    return RedirectResponse("/", status_code=307)


@app.get("/nang-cao")
def trang_nang_cao() -> RedirectResponse:
    return RedirectResponse("/", status_code=307)


@app.get("/api/trang-thai")
def api_trang_thai() -> dict:
    return {**anh_trang_thai(), "may": may_moc(), "viec": VIEC.anh()}


@app.post("/api/chon-kich-ban")
async def api_chon_kich_ban(req: Request) -> dict:
    d = await req.json()
    p = dat_kich_ban(d.get("ten", ""))
    return {"ok": True, "ten": p.name}


@app.post("/api/kich-ban")
async def api_luu_kich_ban(req: Request) -> dict:
    d = await req.json()
    if not isinstance(d.get("canh"), list) or not d["canh"]:
        raise HTTPException(400, "Kich ban phai co it nhat mot canh.")
    ids = [c.get("id", "") for c in d["canh"]]
    if len(set(ids)) != len(ids) or not all(ids):
        raise HTTPException(400, "Moi canh phai co id rieng, khong duoc trung hay de trong.")
    dich = duong_kich_ban()
    sao = C.VAO / f"{dich.stem}.truoc_{time.strftime('%Y%m%d_%H%M%S')}.json"
    if dich.exists():
        shutil.copy(dich, sao)
    dich.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "sao_luu": sao.name}


@app.post("/api/chay/{buoc}")
async def api_chay(buoc: str, req: Request) -> dict:
    d = {}
    try:
        d = await req.json()
    except Exception:
        pass
    canh = d.get("canh")
    lam_lai = bool(d.get("lam_lai"))
    kb = duong_kich_ban()

    if buoc == "tts":
        lenh = [PY_VENV, "scripts/01_tts.py"]
    elif buoc == "hoat_hinh":
        lenh = [PY_VENV, "scripts/02_hoat_hinh.py"]
    elif buoc == "ghep":
        lenh = [PY_VENV, "scripts/03_ghep.py"]
    elif buoc == "tat_ca":
        lenh = [PY_VENV, "cong_cu/chay_het.py"]
    else:
        raise HTTPException(404, f"Khong co buoc '{buoc}'")

    lenh += ["--kich-ban", str(kb.relative_to(C.GOC))]
    if buoc in ("ghep", "tat_ca"):
        lenh += ["--ra", str(duong_video_cuoi().relative_to(C.GOC))]
    if canh and buoc in ("tts", "hoat_hinh"):
        lenh += ["--canh", canh]
    if lam_lai and buoc in ("tts", "hoat_hinh", "tat_ca"):
        lenh += ["--lam-lai"]

    try:
        return {"ok": True, "viec": VIEC.chay(buoc, lenh, kich_ban=kb.name)}
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.post("/api/dung")
def api_dung() -> dict:
    return {"ok": VIEC.dung()}


@app.get("/api/log")
async def api_log(tu: int = 0, kenh: str = "") -> StreamingResponse:
    vn = VIEC_MAY.get(kenh, VIEC)          # kenh=gpu0|gpu1: nhat ky cua may ve do (Xuong); trong: viec nang cao

    async def phat():
        moc = tu
        while True:
            moi, moc = vn.doc_log(moc)
            for d in moi:
                yield f"data: {json.dumps(d, ensure_ascii=False)}\n\n"
            yield (f"event: trang_thai\ndata: "
                   f"{json.dumps({**vn.anh(), 'moc': moc}, ensure_ascii=False)}\n\n")
            await asyncio.sleep(1)

    return StreamingResponse(phat(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache",
                                      "X-Accel-Buffering": "no"})


@app.post("/api/tai-len/{loai}")
async def api_tai_len(loai: str, files: list[UploadFile] = File(...)) -> dict:
    if loai == "canh":
        dich, hop_le = C.CANH, {".png", ".jpg", ".jpeg", ".webp"}
    elif loai == "giong_mau":
        dich, hop_le = C.VAO, {".wav", ".mp3", ".flac"}
    elif loai == "kich_ban":
        dich, hop_le = C.VAO, {".json", ".txt"}
    else:
        raise HTTPException(404, f"Khong nhan loai '{loai}'")
    dich.mkdir(parents=True, exist_ok=True)

    xong = []
    for f in files:
        ten = Path(f.filename or "").name
        if Path(ten).suffix.lower() not in hop_le:
            raise HTTPException(400, f"'{ten}': chi nhan {', '.join(sorted(hop_le))}")
        if loai == "giong_mau":
            ten = "giong_mau.wav"
        elif loai == "kich_ban":
            ten = "kich_ban.json" if ten.lower().endswith(".json") else "kich_ban_thoai.txt"
        (dich / ten).write_bytes(await f.read())
        xong.append(ten)

        if ten == "kich_ban_thoai.txt":
            r = subprocess.run(
                [PY_VENV, "cong_cu/doc_kich_ban_thoai.py", str(dich / ten),
                 "--kieu", "ken_burns", "--ghi"],
                cwd=str(C.GOC), capture_output=True, text=True, timeout=60)
            if r.returncode:
                raise HTTPException(400, f"Khong doc duoc kich ban:\n{r.stdout}{r.stderr}"[:800])
            xong.append("-> da doi sang kich_ban.json: " + r.stdout.strip().splitlines()[0])
    return {"ok": True, "file": xong}


@app.get("/media/{loai}/{ten}")
def api_media(loai: str, ten: str):
    ten = Path(ten).name  # chan di nguoc thu muc
    goc = {"anh": C.CANH, "tieng": C.TIENG, "clip": C.CLIP, "ra": C.RA}.get(loai)
    if goc is None:
        raise HTTPException(404, "loai khong hop le")
    p = (goc / ten).resolve()
    if not str(p).startswith(str(goc.resolve())) or not p.exists():
        raise HTTPException(404, "khong thay file")
    return FileResponse(p)


@app.get("/tai-ve")
def api_tai_ve():
    """Tai video cuoi ve may. Dat ten file theo ten video trong kich ban."""
    p = duong_video_cuoi()
    if not p.exists():
        raise HTTPException(404, "Chua co video cuoi.")
    try:
        ten = C.doc_kich_ban(duong_kich_ban()).ten_video
    except Exception:
        ten = p.stem
    an = "".join(ch for ch in ten if ch.isalnum() or ch in " -_").strip() or "video"
    return FileResponse(p, media_type="video/mp4", filename=f"{an}.mp4")


@app.get("/api/so-do")
def api_so_do() -> JSONResponse:
    d = {}
    for ten in ("do_tts", "do_video", "do_ghep"):
        p = C.LOGS / f"{ten}.json"
        if p.exists():
            try:
                d[ten] = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    return JSONResponse(d)


# ------------------------------------------------------ du an: go cau chuyen -> video

sys.path.insert(0, str(C.GOC / "cong_cu"))
import len_kich_ban as LKB  # noqa: E402

DU_AN = C.RA / "du_an"
ID_HOP_LE = re.compile(r"^[0-9a-z_]{6,40}$")
ANH_HOP_LE = {".png", ".jpg", ".jpeg", ".webp"}
NHAC_HOP_LE = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}
TAM = ("tien_do", "co_video", "mb_video", "clip_co")     # truong tinh luc doc, khong ghi xuong dia


def _thu_muc(id_: str) -> Path:
    if not ID_HOP_LE.match(id_ or ""):
        raise HTTPException(400, "Mã dự án không hợp lệ.")
    d = DU_AN / id_
    if not (d / "du_an.json").exists():
        raise HTTPException(404, "Không thấy dự án.")
    return d


def _doc(d: Path) -> dict:
    da = json.loads((d / "du_an.json").read_text(encoding="utf-8"))
    td = d / "tien_do.json"
    da["tien_do"] = json.loads(td.read_text(encoding="utf-8")) if td.exists() else None
    v = d / "video.mp4"
    da["co_video"] = v.exists()
    da["mb_video"] = round(v.stat().st_size / 1048576, 1) if v.exists() else None
    da["clip_co"] = [(d / "clip" / f"c{i + 1:02d}.mp4").exists() for i in range(len(da.get("canh") or []))]
    # Tat may giua chung thi file van ghi "dang_chay" ma khong con viec nao — bao dung su that.
    viec = VIEC.anh()
    if da.get("trang_thai") == "dang_chay" and not (viec.get("dang_chay") and viec.get("ten") == f"du_an:{d.name}"):
        da["trang_thai"] = "dung_giua_chung"
    return da


def _luu(d: Path, da: dict) -> None:
    (d / "du_an.json").write_text(json.dumps({k: v for k, v in da.items() if k not in TAM},
                                             ensure_ascii=False, indent=2), encoding="utf-8")


def _bat_comfy() -> None:
    import urllib.request
    try:
        urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=3)
    except Exception:
        subprocess.run(["bash", str(C.GOC / "cong_cu" / "comfy.sh"), "len"], cwd=str(C.GOC), check=True)


async def _len(da: dict, bien_the: int = 0) -> dict:
    await asyncio.to_thread(_bat_comfy)
    return await asyncio.to_thread(LKB.len_kich_ban, da["cau_chuyen"], float(da.get("giay", 10)),
                                   da.get("nhip", "nhanh"), da.get("nhan_vat", ""),
                                   da.get("phong_cach_goi_y", ""), bien_the)


@app.get("/api/phong-cach")
def api_phong_cach() -> list:
    """Danh sach phong cach dung chung voi bo len kich ban — giao dien khong giu ban sao rieng."""
    return [{"khoa": k, "ten": t, "mo_ta": m} for k, t, m in LKB.PHONG_CACH_MAU]


@app.get("/api/may")
def api_may() -> dict:
    return {"may": may_moc(), "viec": VIEC.anh()}


@app.get("/api/du-an")
def api_ds_du_an() -> list:
    ra = []
    for p in sorted(DU_AN.glob("*/du_an.json"), reverse=True):
        try:
            da = _doc(p.parent)
        except Exception:
            continue
        canh = da.get("canh") or []
        ra.append({"id": p.parent.name, "tieu_de": da.get("tieu_de") or "(chưa có tiêu đề)",
                   "trang_thai": da.get("trang_thai"), "so_canh": len(canh),
                   "giay": round(sum(float(c.get("giay", 0)) for c in canh), 1),
                   "co_video": da["co_video"], "tao_luc": da.get("tao_luc"),
                   "cau_chuyen": (da.get("cau_chuyen") or "")[:160]})
    return ra


@app.post("/api/du-an/len-kich-ban")
async def api_len_kich_ban(cau_chuyen: str = Form(...), giay: float = Form(10), nhip: str = Form("nhanh"),
                           phong_cach: str = Form(""), bam_anh: bool = Form(False),
                           anh_mau: UploadFile | None = File(None), nhac: UploadFile | None = File(None)) -> dict:
    cau_chuyen = cau_chuyen.strip()
    if len(cau_chuyen) < 10:
        raise HTTPException(400, "Kể câu chuyện dài hơn một chút nhé (ít nhất 10 ký tự).")
    if nhip not in LKB.NHIP:
        raise HTTPException(400, f"Nhịp phải là: {', '.join(LKB.NHIP)}")
    id_ = time.strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(2)
    d = DU_AN / id_
    d.mkdir(parents=True)
    da = {"id": id_, "cau_chuyen": cau_chuyen, "giay": max(3.0, min(180.0, float(giay))), "nhip": nhip,
          "phong_cach_goi_y": phong_cach.strip()[:300], "bam_anh": bool(bam_anh), "anh_mau": None,
          "nhac": None, "nhan_vat": "", "seed": 1234, "bien_the": 0, "trang_thai": "dang_len_kich_ban",
          "tao_luc": time.strftime("%Y-%m-%d %H:%M:%S")}
    for f, khoa, hop in ((anh_mau, "anh_mau", ANH_HOP_LE), (nhac, "nhac", NHAC_HOP_LE)):
        if f is not None and f.filename:
            duoi = Path(f.filename).suffix.lower()
            if duoi not in hop:
                shutil.rmtree(d, ignore_errors=True)
                raise HTTPException(400, f"'{f.filename}': chỉ nhận {', '.join(sorted(hop))}")
            (d / f"{khoa}{duoi}").write_bytes(await f.read())
            da[khoa] = f"{khoa}{duoi}"
    _luu(d, da)
    try:
        if da["anh_mau"]:
            await asyncio.to_thread(_bat_comfy)
            da["nhan_vat"] = await asyncio.to_thread(LKB.mo_ta_anh, d / da["anh_mau"])
        kb = await _len(da)
    except Exception as e:
        da.update(trang_thai="loi", loi=str(e)[:600])
        _luu(d, da)
        raise HTTPException(502, f"Không lên được kịch bản: {e}")
    da.update(tieu_de=kb["tieu_de"], phong_cach=kb["phong_cach"], canh=kb["canh"],
              ngon_ngu=kb.get("ngon_ngu"), trang_thai="nhap", loi="")
    _luu(d, da)
    return _doc(d)


@app.get("/api/du-an/{id_}")
def api_du_an(id_: str) -> dict:
    return _doc(_thu_muc(id_))


@app.put("/api/du-an/{id_}")
async def api_sua_du_an(id_: str, req: Request) -> dict:
    d = _thu_muc(id_)
    da = _doc(d)
    if da.get("trang_thai") == "dang_chay":
        raise HTTPException(409, "Đang tạo video — đợi xong hoặc bấm Dừng rồi mới sửa.")
    moi = await req.json()
    canh = moi.get("canh")
    if not isinstance(canh, list) or not canh:
        raise HTTPException(400, "Cần ít nhất một cảnh.")
    sach = []
    for i, c in enumerate(canh, 1):
        p = str(c.get("prompt", "")).strip()
        if not p:
            raise HTTPException(400, f"Cảnh {i} chưa có mô tả.")
        try:
            g = float(c.get("giay", 1.5))
        except (TypeError, ValueError):
            raise HTTPException(400, f"Cảnh {i}: số giây không hợp lệ.")
        chu = [{"noi_dung": str(k.get("noi_dung", "")).strip()[:80],
                "kieu": k.get("kieu") if k.get("kieu") in LKB.KIEU_CHU else "nhan"}
               for k in (c.get("chu") or [])[:2] if isinstance(k, dict) and str(k.get("noi_dung", "")).strip()]
        sach.append({"prompt": p[:600], "giay": round(max(0.4, min(10.0, g)), 2),
                     "co_nhan_vat": bool(c.get("co_nhan_vat")), "chu": chu})
    da.update(canh=sach, trang_thai="nhap",
              tieu_de=str(moi.get("tieu_de", da.get("tieu_de", ""))).strip()[:80],
              phong_cach=str(moi.get("phong_cach", da.get("phong_cach", ""))).strip()[:300],
              bam_anh=bool(moi.get("bam_anh", da.get("bam_anh"))))
    _luu(d, da)
    return _doc(d)


@app.post("/api/du-an/{id_}/len-lai")
async def api_len_lai(id_: str) -> dict:
    d = _thu_muc(id_)
    da = _doc(d)
    if da.get("trang_thai") == "dang_chay":
        raise HTTPException(409, "Đang tạo video, không lên lại được.")
    da["bien_the"] = int(da.get("bien_the", 0)) + 1
    try:
        kb = await _len(da, da["bien_the"])
    except Exception as e:
        raise HTTPException(502, f"Không lên được kịch bản: {e}")
    da.update(tieu_de=kb["tieu_de"], phong_cach=kb["phong_cach"], canh=kb["canh"], trang_thai="nhap", loi="")
    _luu(d, da)
    return _doc(d)


@app.post("/api/du-an/{id_}/tao")
def api_tao_video(id_: str) -> dict:
    d = _thu_muc(id_)
    if not _doc(d).get("canh"):
        raise HTTPException(400, "Chưa có cảnh nào.")
    try:
        viec = VIEC.chay(f"du_an:{id_}", [PY_VENV, "cong_cu/du_an.py", str(d / "du_an.json")], kich_ban=id_)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"ok": True, "viec": viec}


@app.delete("/api/du-an/{id_}")
def api_xoa_du_an(id_: str) -> dict:
    d = _thu_muc(id_)
    if _doc(d).get("trang_thai") == "dang_chay":
        raise HTTPException(409, "Đang tạo video, không xoá được.")
    shutil.rmtree(d)
    return {"ok": True}


@app.get("/du-an/{id_}/video")
def du_an_video(id_: str):
    v = _thu_muc(id_) / "video.mp4"
    if not v.exists():
        raise HTTPException(404, "Chưa có video.")
    return FileResponse(v, media_type="video/mp4")


@app.get("/du-an/{id_}/tai-ve")
def du_an_tai_ve(id_: str):
    d = _thu_muc(id_)
    v = d / "video.mp4"
    if not v.exists():
        raise HTTPException(404, "Chưa có video.")
    ten = json.loads((d / "du_an.json").read_text(encoding="utf-8")).get("tieu_de") or id_
    an = "".join(ch for ch in ten if ch.isalnum() or ch in " -_").strip() or "video"
    return FileResponse(v, media_type="video/mp4", filename=f"{an}.mp4")


@app.get("/du-an/{id_}/anh-mau")
def du_an_anh_mau(id_: str):
    d = _thu_muc(id_)
    ten = json.loads((d / "du_an.json").read_text(encoding="utf-8")).get("anh_mau")
    if not ten or not (d / ten).exists():
        raise HTTPException(404, "Không có ảnh mẫu.")
    return FileResponse(d / ten)


@app.get("/du-an/{id_}/clip/{so}")
def du_an_clip(id_: str, so: int):
    p = _thu_muc(id_) / "clip" / f"c{so:02d}.mp4"
    if not p.exists():
        raise HTTPException(404, "Cảnh chưa render.")
    return FileResponse(p, media_type="video/mp4")



# ------------------------------------------------ xuong: tu viet tung canh -> tao -> merge

import hang_doi as HD  # noqa: E402
import model_xuong as MX
HD.MAY_BAT = list(HD.MAY_VE)  # Xưởng uses both GPUs when ComfyUI mode is enabled.
_dang_doc_model = set()
import xuong as XG     # noqa: E402
import video_bao_mat as VB
import tep_bao_mat as TB
import tach_nen as TN  # noqa: E402
import nhap_kich_ban as NKB  # noqa: E402
import tao_mau_word as TMW   # noqa: E402

MIME_DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

ID_CANH = re.compile(r"^[a-z0-9]{2,16}$")
GIONG_HOP_LE = {".wav", ".mp3", ".flac", ".m4a", ".ogg"}
TAM_XG = ("trang_thai_canh", "hang_doi", "tien_do", "co_video", "mb_video", "video_moi", "merge")
_khoa_xg = threading.Lock()


def _xg_thu_muc(id_: str) -> Path:
    if not ID_HOP_LE.match(id_ or ""):
        raise HTTPException(400, "Mã dự án không hợp lệ.")
    d = XG.XUONG / id_
    if not (d / "du_an.json").exists():
        raise HTTPException(404, "Không thấy dự án.")
    return d


def _xg_file(d: Path) -> dict:
    return json.loads((d / "du_an.json").read_text(encoding="utf-8"))


def _xg_luu(d: Path, da: dict) -> None:
    tam = d / "du_an.json.tmp"
    tam.write_text(json.dumps({k: v for k, v in da.items() if k not in TAM_XG}, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    tam.replace(d / "du_an.json")


def _xg_doc(d: Path) -> dict:
    da, ch, q = _xg_file(d), XG.cau_hinh(), HD.doc()
    chay = HD.dang_chay(q)                                   # {may ve: viec} — moi GPU toi da mot viec
    cua_da = [v for v in chay.values() if v.get("du_an") == d.name]
    tt = {}
    for c in da.get("canh") or []:
        s = XG.trang_thai_canh(c, da, d, ch)
        mp4, wav = d / "clip" / f"{c['id']}.brd", d / "tieng" / f"{c['id']}.wav"
        s["phien_clip"] = int(mp4.stat().st_mtime) if mp4.exists() else 0
        s["phien_tieng"] = int(wav.stat().st_mtime) if wav.exists() else 0
        dang_ve = next((v for v in cua_da if v.get("loai") == "canh" and v.get("canh") == c["id"]), None)
        if dang_ve:
            s["trang_thai"], s["may"] = "dang_tao", dang_ve.get("may")
            s["tien_do"] = XG._json(d / "tien_do" / f"{c['id']}.json") or {"pha": "Đang chuẩn bị", "phan_tram": 1,
                                                                            "bat_dau": dang_ve.get("bat_dau")}
        else:
            vt = next((i for i, v in enumerate(q["cho"]) if v.get("loai") == "canh" and v.get("du_an") == d.name
                       and v.get("canh") == c["id"]), None)
            if vt is not None:
                s["trang_thai"], s["vi_tri"] = "cho", vt + 1
        tt[c["id"]] = s
    da["trang_thai_canh"] = tt
    if da.get("dang_viet_prompt") and d.name not in _dang_viet:      # server vua khoi dong lai giua luc viet
        _bat_viet_prompt(d)
    cuoi = next((x for x in reversed(q.get("xong") or []) if x.get("du_an") == d.name and x.get("loai") == "merge"), None)
    da["merge"] = {
        "trang_thai": "dang" if any(v.get("loai") == "merge" for v in cua_da)
        else ("cho" if any(v.get("loai") == "merge" and v.get("du_an") == d.name for v in q["cho"]) else None),
        "loi": cuoi["loi"] if cuoi and not cuoi.get("ok") else ""}
    da["hang_doi"] = {"dang": cua_da, "dang_viec_khac": any(v.get("du_an") != d.name for v in chay.values()),
                      "may_ranh": max(0, len(HD.MAY_BAT) - len(chay)), "so_may": len(HD.MAY_BAT),
                      "cho_cua_du_an": sum(1 for v in q["cho"] if v.get("du_an") == d.name), "tong_cho": len(q["cho"]),
                      "chay": bool(chay)}
    td = d / "tien_do.json"
    da["tien_do"] = json.loads(td.read_text(encoding="utf-8")) if td.exists() else None
    v = VB.merged_path(d)
    da["co_video"] = v.exists()
    da["mb_video"] = round(v.stat().st_size / 1048576, 1) if v.exists() else None
    b = d / XG.BANG
    da["co_bang"], da["phien_bang"] = b.exists(), (int(b.stat().st_mtime) if b.exists() else 0)
    da["video_moi"] = bool(v.exists() and da.get("dau_merge") == XG.dau_ban_ghep(da, d, ch)
                           and all(s["trang_thai"] == "xong" for s in tt.values()))
    return da


VIEC_MAY = {t: ViecNen(C.LOGS / "viec" / t, C.GOC) for t in HD.MAY_VE}   # moi may ve (GPU) mot tien trinh


def _model_busy():
    q = HD.doc()
    return bool(q["cho"] or HD.dang_chay(q) or _dang_viet or _dang_doc_model or VIEC.dang_chay
                or any(v.dang_chay for v in VIEC_MAY.values()))


@app.get("/api/xuong-model")
def model_status():
    return {**MX.status(), "work_busy": _model_busy()}


@app.post("/api/xuong-model/{action}")
def model_switch(action: str):
    if action not in ("start", "stop"):
        raise HTTPException(400, "Thao tác không hợp lệ.")
    try:
        return MX.request(action, _model_busy)
    except RuntimeError as e:
        raise HTTPException(409, str(e))


@app.middleware("http")
async def model_use_guard(req: Request, call_next):
    # Lease covers job submission; background jobs acquire their own lease.
    needs_model = req.method == "POST" and re.fullmatch(
        r"/api/xuong/[^/]+/(?:canh/[^/]+/tao|tao-het|merge|nhap-kich-ban|tep/anh_mau)", req.url.path)
    if not needs_model:
        return await call_next(req)
    if not await asyncio.to_thread(AUTH.session_valid, req.cookies.get(AUTH.COOKIE, "")):
        return JSONResponse({"detail": "Vui lòng đăng nhập."}, 401)
    from contextlib import ExitStack
    with ExitStack() as stack:
        try:
            stack.enter_context(MX.lease())
            state = await asyncio.to_thread(MX.status)
            if not state["ready"]:
                raise RuntimeError("ComfyUI chưa sẵn sàng trên đủ 2 GPU. Bấm Bật ComfyUI để khôi phục.")
        except RuntimeError as e:
            return JSONResponse({"detail": str(e)}, 409)
        return await call_next(req)


def _bat_hang_doi() -> None:
    try:
        with MX.lease():
            _bat_hang_doi_ready()
    except RuntimeError:
        return


def _bat_hang_doi_ready() -> None:
    """Bat tien trinh cho cac may ve dang nghi — chi bat du so viec bat dau duoc NGAY (vd merge con doi canh
    cua du an do thi khong bat), tranh tien trinh vua bat da thoat."""
    q = HD.doc()
    if not q["cho"] or not MX.status()["ready"]:
        return
    dang_len = [t for t in HD.MAY_BAT if VIEC_MAY[t].anh().get("dang_chay") and not HD.dang_song(t)]
    nghi = [t for t in HD.MAY_BAT if not HD.dang_song(t) and not VIEC_MAY[t].anh().get("dang_chay")]
    if not nghi:
        return
    so = HD.so_viec_lay_ngay(q, len(nghi) + len(dang_len)) - len(dang_len)   # may dang khoi dong se lay truoc
    for t in nghi[:max(0, so)]:
        VIEC_MAY[t].chay("hang_doi", ["env", f"CUDA_VISIBLE_DEVICES={HD.MAY_VE[t]['gpu']}", PY_VENV,
                                      "cong_cu/hang_doi.py", t])


async def _canh_gac() -> None:
    while True:
        try:
            await asyncio.to_thread(_bat_hang_doi)
        except Exception:
            pass
        await asyncio.sleep(4)


@app.on_event("startup")
async def _khoi_dong_canh_gac() -> None:
    asyncio.create_task(_canh_gac())


@app.get("/api/xuong/cau-hinh")
def xg_cau_hinh() -> dict:
    return {**XG.cau_hinh(), "duoi": XG.DUOI, "cam_xuc": list(C.CAM_XUC), "fps": XG.FPS, "che_do": list(XG.DA.CHE_DO),
            "phong_cach_mau": [{"ten": t, "mo_ta": m} for _, t, m in LKB.PHONG_CACH_MAU]}


@app.get("/api/xuong")
def xg_ds() -> list:
    ra = []
    for p in sorted(XG.XUONG.glob("*/du_an.json"), key=lambda x: x.stat().st_mtime, reverse=True):
        try:
            da = _xg_doc(p.parent)
        except Exception:
            continue
        tt = da["trang_thai_canh"].values()
        ra.append({"id": p.parent.name, "ten": da.get("ten") or "Dự án", "so_canh": len(da.get("canh") or []),
                   "so_xong": sum(1 for s in tt if s["trang_thai"] == "xong"),
                   "so_dang_ve": sum(1 for s in tt if s["trang_thai"] == "dang_tao"),
                   "so_cho": sum(1 for s in tt if s["trang_thai"] == "cho"),
                   "phan_tram_dang_ve": sum((s.get("tien_do") or {}).get("phan_tram") or 0 for s in tt if s["trang_thai"] == "dang_tao"),
                   "dang_chay": any(s["trang_thai"] in ("dang_tao", "cho") for s in tt) or bool(da["merge"]["trang_thai"]),
                   "co_video": da["co_video"], "sua_luc": da.get("sua_luc") or da.get("tao_luc")})
    return ra


@app.post("/api/xuong")
async def xg_moi(req: Request) -> dict:
    try:
        vao = await req.json()
    except Exception:
        vao = {}
    id_ = time.strftime("%Y%m%d_%H%M%S_") + secrets.token_hex(2)
    d = XG.XUONG / id_
    d.mkdir(parents=True)
    bay_gio = time.strftime("%Y-%m-%d %H:%M:%S")
    _xg_luu(d, {"id": id_, "ten": str(vao.get("ten") or "Dự án mới")[:100],
                "phong_cach": LKB.PHONG_CACH_MAU[0][2], "anh_mau": None, "mo_ta_anh": "",
                "giong": {"mau": None, "cam_xuc": "binh_thuong"}, "nhac": None, "hieu_ung_phim": True, "che_do": "chuan",
                "seed": 1234, "canh": [{"id": secrets.token_hex(3), "prompt": "", "loi_doc": "", "giay": 5, "anh": "khong"}],
                "tao_luc": bay_gio, "sua_luc": bay_gio})
    return _xg_doc(d)


@app.get("/api/xuong/{id_}")
def xg_xem(id_: str) -> dict:
    return _xg_doc(_xg_thu_muc(id_))


@app.put("/api/xuong/{id_}")
async def xg_sua(id_: str, req: Request) -> dict:
    d = _xg_thu_muc(id_)
    moi = await req.json()
    with _khoa_xg:
        da = _xg_file(d)
        if "ten" in moi:
            da["ten"] = str(moi["ten"]).strip()[:100] or "Dự án"
        if "phong_cach" in moi:
            da["phong_cach"] = str(moi["phong_cach"])[:800]
        if "mo_ta_anh" in moi:
            da["mo_ta_anh"] = str(moi["mo_ta_anh"])[:800]
        if "hieu_ung_phim" in moi:
            da["hieu_ung_phim"] = bool(moi["hieu_ung_phim"])
        if moi.get("che_do") in XG.DA.CHE_DO:
            da["che_do"] = moi["che_do"]
        if isinstance(moi.get("giong"), dict) and moi["giong"].get("cam_xuc") in C.CAM_XUC:
            da.setdefault("giong", {})["cam_xuc"] = moi["giong"]["cam_xuc"]
        if "canh" in moi:
            if not isinstance(moi["canh"], list) or not moi["canh"]:
                raise HTTPException(400, "Cần ít nhất một cảnh.")
            sach, thay_roi = [], set()
            cu = {c.get("id"): c for c in da.get("canh") or []}
            for c in moi["canh"]:
                cid = str(c.get("id") or "")
                if not ID_CANH.match(cid) or cid in thay_roi:
                    cid = secrets.token_hex(3)
                thay_roi.add(cid)
                try:
                    g = float(c.get("giay", 5))
                except (TypeError, ValueError):
                    g = 5.0
                truoc = cu.get(cid, {})
                p = str(c.get("prompt", ""))[:1500]
                if not p.strip() and truoc.get("prompt_tu_dong"):
                    p = truoc.get("prompt", "")     # trang chua kip nhan prompt may vua viet -> khong ghi de thanh trong
                item = {"id": cid, "prompt": p, "loi_doc": str(c.get("loi_doc", ""))[:2000],
                        "giay": round(max(1.0, min(60.0, g)), 2),
                        "anh": c.get("anh") if c.get("anh") in XG.KIEU_ANH else "khong",
                        "muc": str(c.get("muc", truoc.get("muc", "")) or "")[:80]}
                if truoc.get("prompt_tu_dong") and p.strip() == (truoc.get("prompt") or "").strip():
                    item["prompt_tu_dong"] = True   # nguoi dung sua prompt thi thanh prompt cua ho
                if truoc.get("tao_sau_viet"):
                    item["tao_sau_viet"] = True
                sach.append(item)
            da["canh"] = sach
        da["sua_luc"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _xg_luu(d, da)
    return _xg_doc(d)


async def _doc_anh_nen(d: Path, ten: str) -> None:
    try:
        with MX.lease():
            await _doc_anh_job(d, ten)
    finally:
        _dang_doc_model.discard(d.name)


async def _doc_anh_job(d: Path, ten: str) -> None:
    try:
        await asyncio.to_thread(_bat_comfy)
        mo_ta, loi = await asyncio.to_thread(LKB.mo_ta_anh, d / ten), ""
    except Exception as e:
        mo_ta, loi = "", str(e)[:300]
    try:          # bang tham chieu cho kieu "Giu nhan vat" — tach nen BiRefNet qua ComfyUI, vai giay
        await asyncio.to_thread(TN.dung_bang_tu_anh, d / ten, d / XG.BANG)
    except Exception as e:
        loi = (loi + " · " if loi else "") + f"Không dựng được bảng tham chiếu: {str(e)[:200]}"
    with _khoa_xg:
        da = _xg_file(d)
        if da.get("anh_mau") == ten:            # chua bi doi sang anh khac trong luc doc
            if not (da.get("mo_ta_anh") or "").strip():
                da["mo_ta_anh"] = mo_ta
            da["dang_doc_anh"], da["loi_doc_anh"] = False, loi
            _xg_luu(d, da)


@app.post("/api/xuong/{id_}/tep/{loai}")
async def xg_tai_tep(id_: str, loai: str, file: UploadFile = File(...)) -> dict:
    d = _xg_thu_muc(id_)
    hop = {"anh_mau": ANH_HOP_LE, "giong_mau": GIONG_HOP_LE, "nhac": NHAC_HOP_LE}.get(loai)
    if hop is None:
        raise HTTPException(404, "Loại tệp không hợp lệ.")
    duoi = Path(file.filename or "").suffix.lower()
    if duoi not in hop:
        raise HTTPException(400, f"Chỉ nhận {', '.join(sorted(hop))}")
    for cu in d.glob(f"{loai}.*"):
        cu.unlink()
    ten = f"{loai}{duoi}"
    (d / ten).write_bytes(await file.read())
    with _khoa_xg:
        da = _xg_file(d)
        if loai == "giong_mau":
            da.setdefault("giong", {})["mau"] = ten
        else:
            da[loai] = ten
        if loai == "anh_mau":
            da.update(mo_ta_anh="", dang_doc_anh=True, loi_doc_anh="")
        _xg_luu(d, da)
    if loai == "anh_mau":
        _dang_doc_model.add(d.name)
        asyncio.create_task(_doc_anh_nen(d, ten))
    return _xg_doc(d)


@app.delete("/api/xuong/{id_}/tep/{loai}")
def xg_bo_tep(id_: str, loai: str) -> dict:
    d = _xg_thu_muc(id_)
    if loai not in ("anh_mau", "giong_mau", "nhac"):
        raise HTTPException(404, "Loại tệp không hợp lệ.")
    with _khoa_xg:
        da = _xg_file(d)
        for cu in d.glob(f"{loai}.*"):
            cu.unlink()
        if loai == "giong_mau":
            da.setdefault("giong", {})["mau"] = None
        else:
            da[loai] = None
        if loai == "anh_mau":
            da.update(mo_ta_anh="", dang_doc_anh=False)
            (d / XG.BANG).unlink(missing_ok=True)
        _xg_luu(d, da)
    return _xg_doc(d)


# ---------------------------------------------------- nhap kich ban + may viet prompt hinh

@app.get("/mau/{ten}")
def tai_mau_word(ten: str):
    """File Word mau de nguoi dung tu viet loi doc + prompt hinh (cong_cu/tao_mau_word.py)."""
    if ten not in ("mau_kich_ban_bang.docx", "mau_kich_ban_dong.docx"):
        raise HTTPException(404, "Không có file mẫu này.")
    p = TMW.MAU / ten
    if not p.exists():
        TMW.main()
    return FileResponse(p, media_type=MIME_DOCX, filename=ten)


@app.get("/xuong/{id_}/xuat-word")
def xg_xuat_word(id_: str):
    """Du an -> Word dang bang: sua prompt trong Word roi Nhap kich ban lai (Thay toan bo canh)."""
    d = _xg_thu_muc(id_)
    da = _xg_file(d)
    ra = TMW.xuat_du_an(da, d / ".kich_ban_xuat.docx")
    ten = re.sub(r"[^\w\- ]+", "", NKB.bo_dau(da.get("ten") or "du an")).strip()[:60] or "du_an"
    return FileResponse(ra, media_type=MIME_DOCX, filename=f"{ten}.docx")


_dang_viet: set[str] = set()          # du an dang co luong viet prompt


def _can_viet(c: dict) -> bool:
    return not (c.get("prompt") or "").strip() and bool((c.get("loi_doc") or "").strip())


def _viet_prompt_nen(d: Path) -> None:
    try:
        with MX.lease():
            _viet_prompt_job(d)
    finally:
        _dang_viet.discard(d.name)


def _viet_prompt_job(d: Path) -> None:
    """Luong nen: viet prompt hinh (Gemma E2B, ComfyUI nao ranh hon) cho moi canh co loi doc ma o Prompt hinh con
    trong — tung canh, luu ngay de trang thay dan. Canh da bam Tao ma chua co prompt thi viet xong tu xep ve."""
    bo_qua: set[str] = set()
    try:
        while True:
            with _khoa_xg:
                da = _xg_file(d)
                canh = da.get("canh") or []
                ds = [i for i, c in enumerate(canh) if _can_viet(c) and c["id"] not in bo_qua]
                # canh nguoi dung da bam Tao viet truoc
                ds.sort(key=lambda i: (not canh[i].get("tao_sau_viet"), i))
                if not ds:
                    da.pop("dang_viet_prompt", None)
                    _xg_luu(d, da)
                    return
                da["dang_viet_prompt"] = len(ds)
                _xg_luu(d, da)
                i = ds[0]
                c = dict(canh[i])
                truoc = canh[i - 1].get("loi_doc", "") if i > 0 else ""
                sau = canh[i + 1].get("loi_doc", "") if i + 1 < len(canh) else ""
                pc = da.get("phong_cach") or ""
            try:
                p, loi = LKB.viet_prompt_canh(c["loi_doc"], pc, truoc, sau), ""
            except Exception as e:
                p, loi = "", str(e)[:300]
            xep = False
            with _khoa_xg:
                da = _xg_file(d)
                cc = next((x for x in da.get("canh") or [] if x.get("id") == c["id"]), None)
                if cc is not None and _can_viet(cc) and cc.get("loi_doc") == c["loi_doc"]:
                    if p:
                        cc["prompt"], cc["prompt_tu_dong"] = p, True
                        xep = bool(cc.pop("tao_sau_viet", False))
                    else:
                        bo_qua.add(c["id"])
                        cc.pop("tao_sau_viet", None)
                        da["loi_viet_prompt"] = f"Cảnh {c['id']}: {loi}"
                    _xg_luu(d, da)
            if xep:
                HD.them({"loai": "canh", "du_an": d.name, "canh": c["id"]})
                _bat_hang_doi()
    except Exception as e:
        print(f"[viet prompt] {d.name}: {e}", flush=True)
    finally:
        _dang_viet.discard(d.name)


def _bat_viet_prompt(d: Path) -> None:
    try:
        with MX.lease():
            if d.name in _dang_viet:
                return
            _dang_viet.add(d.name)
            threading.Thread(target=_viet_prompt_nen, args=(d,), daemon=True).start()
    except RuntimeError:
        return


@app.post("/api/xuong/{id_}/nhap-kich-ban")
async def xg_nhap_kich_ban(id_: str, file: UploadFile | None = File(None), chu: str = Form(""),
                           kieu: str = Form("thay"), anh: str = Form("khong"), may_viet: str = Form("1")) -> dict:
    """Kich ban (.docx/.txt/.md hoac chu dan) -> moi doan/hang mot canh co loi doc + prompt hinh neu file co;
    canh thieu prompt thi may viet (tru khi may_viet=0)."""
    d = _xg_thu_muc(id_)
    anh = anh if anh in XG.KIEU_ANH else "khong"
    ch = XG.cau_hinh()
    toi_da = {"tham_chieu": ch.get("giay_toi_da_tham_chieu", 10), "khung_dau": ch["giay_toi_da_khung_dau"]}.get(anh, ch["giay_toi_da"])
    if file is not None and file.filename:
        duoi = Path(file.filename).suffix.lower()
        if duoi not in (".docx", ".txt", ".md"):
            raise HTTPException(400, "Chỉ nhận tệp .docx, .txt hoặc .md")
        tam = d / f".kich_ban{duoi}"
        tam.write_bytes(await file.read())
        try:
            tep = NKB.doc_tep(tam)
        except Exception as e:
            raise HTTPException(400, f"Không đọc được tệp: {str(e)[:200]}")
        finally:
            tam.unlink(missing_ok=True)
    elif chu.strip():
        tep = NKB.doc_tep(chu=chu)
    else:
        raise HTTPException(400, "Chưa có kịch bản — chọn tệp hoặc dán chữ vào.")
    kq = NKB.tach(tep, toi_da - XG.DUOI)
    if not kq["canh"]:
        raise HTTPException(400, "Không tách được cảnh nào từ kịch bản.")
    moi = [{"id": secrets.token_hex(3), "prompt": (x.get("prompt") or "")[:1500], "loi_doc": x["loi_doc"][:2000],
            "anh": anh, "muc": x["muc"][:80], "giay": round(max(1.0, min(60.0, x["giay_du_kien"])), 2)}
           for x in kq["canh"]]
    with _khoa_xg:
        da = _xg_file(d)
        giu = [c for c in da.get("canh") or [] if (c.get("prompt") or "").strip() or (c.get("loi_doc") or "").strip()]
        da["canh"] = (giu if kieu == "them" else []) + moi
        if kq["ten"] and (da.get("ten") or "").strip() in ("", "Dự án mới", "Dự án"):
            da["ten"] = kq["ten"]
        da.pop("loi_viet_prompt", None)
        da["sua_luc"] = time.strftime("%Y-%m-%d %H:%M:%S")
        _xg_luu(d, da)
    thieu = sum(1 for c in moi if _can_viet(c))
    if may_viet != "0" and thieu:
        _bat_viet_prompt(d)
    return {**_xg_doc(d), "nhap": {"so_canh": len(moi), "tong_giay": round(sum(x["giay_du_kien"] for x in kq["canh"]), 1),
                                   "prompt_tu_file": sum(1 for c in moi if c["prompt"].strip()),
                                   "may_viet": thieu if may_viet != "0" else 0, "de_trong": 0 if may_viet != "0" else thieu}}


@app.post("/api/xuong/{id_}/canh/{cid}/tao")
def xg_tao_canh(id_: str, cid: str) -> dict:
    d = _xg_thu_muc(id_)
    try:
        c = XG.tim_canh(_xg_file(d), cid)
    except RuntimeError:
        raise HTTPException(404, "Không thấy cảnh.")
    if _can_viet(c):                      # chua co prompt nhung co loi doc -> may viet roi tu xep ve
        with _khoa_xg:
            da = _xg_file(d)
            XG.tim_canh(da, cid)["tao_sau_viet"] = True
            _xg_luu(d, da)
        _bat_viet_prompt(d)
        return _xg_doc(d)
    if not (c.get("prompt") or "").strip():
        raise HTTPException(400, "Cảnh chưa có prompt hình và lời đọc.")
    HD.them({"loai": "canh", "du_an": id_, "canh": cid})
    _bat_hang_doi()
    return _xg_doc(d)


@app.post("/api/xuong/{id_}/canh/{cid}/bo")
def xg_bo_canh_khoi_hang(id_: str, cid: str) -> dict:
    d = _xg_thu_muc(id_)
    HD.bo(id_, cid)
    return _xg_doc(d)


@app.post("/api/xuong/{id_}/tao-het")
def xg_tao_het(id_: str) -> dict:
    d = _xg_thu_muc(id_)
    da = _xg_doc(d)
    tt = da["trang_thai_canh"]
    # canh da xong nhung ve o che do khac (vd nhap nhanh roi chuyen Chuan) cung ve lai
    them = [c for c in da.get("canh") or []
            if (c.get("prompt") or "").strip() and (tt[c["id"]]["trang_thai"] not in ("xong", "cho", "dang_tao")
                                                     or (tt[c["id"]]["trang_thai"] == "xong" and tt[c["id"]].get("khac_che_do")))]
    for c in them:
        HD.them({"loai": "canh", "du_an": id_, "canh": c["id"]})
    viet = [c["id"] for c in da.get("canh") or [] if _can_viet(c)]
    if viet:                              # canh chua co prompt: may viet xong tung canh thi tu xep ve
        with _khoa_xg:
            moi = _xg_file(d)
            for c in moi.get("canh") or []:
                if c.get("id") in viet and _can_viet(c):
                    c["tao_sau_viet"] = True
            _xg_luu(d, moi)
        _bat_viet_prompt(d)
    _bat_hang_doi()
    return _xg_doc(d)


@app.post("/api/xuong/{id_}/merge")
def xg_merge(id_: str) -> dict:
    d = _xg_thu_muc(id_)
    HD.them({"loai": "merge", "du_an": id_})
    _bat_hang_doi()
    return _xg_doc(d)


@app.post("/api/xuong/{id_}/huy")
def xg_huy(id_: str) -> dict:
    d = _xg_thu_muc(id_)
    HD.bo(id_)
    for t, v in HD.dang_chay(HD.doc()).items():
        if v.get("du_an") != id_:
            continue
        VIEC_MAY[t].dung()     # giet tien trinh cua may do; canh gac se bat lai cho viec cua du an khac
        try:                   # ComfyUI van ve tiep prompt dang do neu khong ngat
            urllib.request.urlopen(urllib.request.Request(
                f"http://127.0.0.1:{HD.MAY_VE[t]['cong']}/interrupt", data=b"", method="POST"), timeout=5)
        except Exception:
            pass
    return _xg_doc(d)


@app.delete("/api/xuong/{id_}")
def xg_xoa(id_: str) -> dict:
    d = _xg_thu_muc(id_)
    q = HD.doc()
    if any(v.get("du_an") == id_ for v in q["cho"]) or any(v.get("du_an") == id_ for v in HD.dang_chay(q).values()):
        raise HTTPException(409, "Dự án đang có việc trong hàng đợi — bấm Huỷ trước.")
    XG.xoa_du_an(d)
    return {"ok": True}


def _xg_tep(d: Path, p: Path, media: str | None = None, ten_tai: str | None = None):
    if not p.resolve().is_relative_to(d.resolve()) or not p.exists():
        raise HTTPException(404, "Không có tệp.")
    return FileResponse(p, media_type=media, filename=ten_tai) if ten_tai else FileResponse(p, media_type=media)


@app.api_route("/xuong/{id_}/clip/{cid}", methods=["GET", "HEAD"])
def xg_clip(id_: str, cid: str, req: Request):
    if not ID_CANH.match(cid):
        raise HTTPException(400, "Mã cảnh không hợp lệ.")
    d = _xg_thu_muc(id_)
    return TB.playback(d / "clip" / f"{cid}.brd", req)


@app.get("/xuong/{id_}/tieng/{cid}")
def xg_tieng(id_: str, cid: str):
    if not ID_CANH.match(cid):
        raise HTTPException(400, "Mã cảnh không hợp lệ.")
    d = _xg_thu_muc(id_)
    return _xg_tep(d, d / "tieng" / f"{cid}.wav", "audio/wav")


@app.get("/xuong/{id_}/tep/{loai}")
def xg_xem_tep(id_: str, loai: str):
    d = _xg_thu_muc(id_)
    da = _xg_file(d)
    ten = (da.get("giong") or {}).get("mau") if loai == "giong_mau" else da.get(loai) if loai in ("anh_mau", "nhac") else None
    if loai == "bang" and (d / XG.BANG).exists():
        ten = XG.BANG
    if not ten:
        raise HTTPException(404, "Không có tệp.")
    return _xg_tep(d, d / ten)


@app.api_route("/xuong/{id_}/video", methods=["GET", "HEAD"])
def xg_video(id_: str, req: Request):
    d = _xg_thu_muc(id_)
    return TB.playback(VB.merged_path(d), req)


@app.get("/xuong/{id_}/tai-ve")
def xg_tai_ve(id_: str, tat_ca: bool = False):
    d = _xg_thu_muc(id_)
    merged = VB.merged_path(d)
    files = sorted(d.rglob("*.brd")) if tat_ca else [merged]
    if not files or any(not p.is_file() or not p.resolve().is_relative_to(d.resolve()) for p in files):
        raise HTTPException(404, "Chưa có tệp mã hóa.")
    # Payload archives contain only BRD files and neutral paths, never instructions.
    entries = [(p, ("parts/" + p.name) if p.parent == d / "clip" else p.name) for p in files]
    filename = merged.stem + ("_parts" if tat_ca else "") + ".zip"
    return TB.zip_response(entries, filename)



@app.get("/bao-mat/cong-cu")
def tai_cong_cu():
    folder = C.GOC / "cong_cu" / "giai_ma_xvideo"
    files = [p for p in folder.iterdir() if p.is_file() and p.suffix in (".py", ".txt", ".bat")]
    return TB.zip_response([(p, "Giai_ma_BRD/" + p.name) for p in files], "Giai_ma_BRD.zip")


@app.get("/bao-mat/key")
def tai_key():
    # Protected by the same admin session middleware as every other private route.
    return FileResponse(Path(os.environ.get("XVIDEO_KEY_FILE", str(VB.KEY_FILE))), media_type="application/octet-stream", filename="video.key")




def cong_trong(bat_dau: int, so_lan: int = 30) -> int:
    """May nay dang chay nhieu app khac (7860, 7870... da co chu). Do cong trong."""
    for c in range(bat_dau, bat_dau + so_lan):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", c)) != 0:
                return c
    raise SystemExit(f"Khong tim duoc cong trong tu {bat_dau}")


def dia_chi_lan() -> str:
    """IP cua may trong mang LAN (khong goi ra ngoai, chi hoi bang dinh tuyen)."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    import uvicorn

    VIEC.don_log_cu()
    chia = os.environ.get("CHIA") == "1"
    cong = int(os.environ["CONG"]) if os.environ.get("CONG") else cong_trong(7880)

    dia = dia_chi_lan() if chia else "127.0.0.1"
    print(f"\n  Giao dien: http://{dia}:{cong}/ — yeu cau dang nhap")
    print(flush=True)

    (C.LOGS / "cong_giao_dien.txt").write_text(str(cong), encoding="utf-8")
    uvicorn.run(app, host="0.0.0.0" if chia else "127.0.0.1", port=cong,
                log_level="warning")
