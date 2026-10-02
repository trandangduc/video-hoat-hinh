"""Buoc 2/3 -- anh canh + wav  ->  ra/clip/<id>.mp4

Canh CO thoai  -> Wan2.2-S2V-14B  (workflows/s2v.json), do dai clip = do dai wav.
Canh KHONG thoai -> Wan2.2-I2V-A14B (workflows/i2v.json), do dai lay tu kich ban.

PHAI chay buoc 1 truoc: khong co wav thi khong biet clip dai bao nhieu.

  python scripts/02_hoat_hinh.py --canh canh_01
  python scripts/02_hoat_hinh.py                 # tat ca canh chua co clip
  python scripts/02_hoat_hinh.py --buoc-lay 20   # so buoc khu nhieu
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chung as C

MAY = "http://127.0.0.1:8188"


# ------------------------------------------------------------- noi ComfyUI

def goi(duong: str, du_lieu: dict | None = None, timeout: int = 30):
    url = f"{MAY}{duong}"
    if du_lieu is None:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read())
    req = urllib.request.Request(
        url, data=json.dumps(du_lieu).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def bat_comfy() -> None:
    try:
        goi("/system_stats", timeout=3)
        C.noi("ComfyUI da chay san")
        return
    except Exception:
        pass
    C.buoc("ComfyUI chua chay -- dang bat")
    r = subprocess.run(["bash", str(C.GOC / "cong_cu" / "comfy.sh"), "len"],
                       capture_output=True, text=True, timeout=400)
    print(r.stdout.strip())
    if r.returncode:
        C.loi("Khong bat duoc ComfyUI. Xem logs/comfy.log")


# --------------------------------------------------------------- theo doi

class DoVram(threading.Thread):
    """Do VRAM dinh trong luc render.

    Lay mau THUA (3s/lan) co chu y: may nay chi co 8 core va CLAUDE.md cua repo
    ben canh da do duoc rang lay mau nvidia-smi day dac lam nhieu chinh phep do.
    """

    def __init__(self, gpu: str):
        super().__init__(daemon=True)
        self.gpu, self.chay = gpu, True
        # Nen = VRAM da bi chiem TRUOC khi ta bat dau (tren may nay la vLLM cua
        # nguoi dung). Bao ca hai so: dinh tuyet doi va phan RIENG pipeline an.
        self.nen_mib = self._doc()
        self.dinh_mib = self.nen_mib

    def _doc(self) -> int:
        try:
            r = subprocess.run(
                ["nvidia-smi", f"--id={self.gpu}",
                 "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=8)
            return int(r.stdout.strip().splitlines()[0])
        except Exception:
            return 0

    @property
    def rieng_mib(self) -> int:
        return max(0, self.dinh_mib - self.nen_mib)

    def run(self) -> None:
        while self.chay:
            self.dinh_mib = max(self.dinh_mib, self._doc())
            time.sleep(3)


_RX_TIEN_DO = re.compile(r"(\d+)/(\d+)\s*\[")


def tien_do_tu_log() -> str:
    """Doc dong tqdm cuoi cung trong log ComfyUI -> 'buoc 7/20'."""
    try:
        duoi = (C.LOGS / "comfy.log").read_bytes()[-4000:].decode("utf-8", "ignore")
        m = None
        for m in _RX_TIEN_DO.finditer(duoi.replace("\r", "\n")):
            pass
        if m:
            return f"buoc {m.group(1)}/{m.group(2)}"
    except Exception:
        pass
    return "dang chay"


def cho_xong(pid: str, nhan: str) -> dict:
    t0 = time.time()
    lan_in = 0.0
    while True:
        try:
            ls = goi(f"/history/{pid}")
        except urllib.error.URLError:
            time.sleep(2)
            continue
        if pid in ls:
            h = ls[pid]
            tt = (h.get("status") or {}).get("status_str")
            if tt == "error":
                C.loi(f"ComfyUI bao loi khi chay {nhan}:\n"
                      f"{json.dumps(h.get('status'), ensure_ascii=False, indent=2)[:1500]}")
            return h
        troi = time.time() - t0
        # Luat cung #6: viec dai phai in tien do, dung de im lang.
        if troi - lan_in >= 15:
            lan_in = troi
            C.noi(f"{nhan}: {tien_do_tu_log()}  ({troi:.0f}s)")
        time.sleep(2)


# ------------------------------------------------------------ dung workflow

def nap_workflow(ten: str) -> dict:
    return json.loads((C.WORKFLOWS / ten).read_text(encoding="utf-8"))


def dat(wf: dict, node: str, khoa: str, gia_tri) -> None:
    wf[node]["inputs"][khoa] = gia_tri


# ------------------------------------------------------------------ Ken Burns
#
# VUNG CAT: (tam_x, tam_y, be_ngang) tinh theo TI LE cua anh goc. Cua so cat
# luon dung ti le khung ra, nen chi can biet cat o dau va rong bao nhieu.
# Nho anh Gemini ve rat chi tiet (ban do, thung ho so, may chieu, anh ghim)
# nen cat vao tung vung se ra nhung CU MAY KHAC NHAU tu CUNG MOT anh.
VUNG = {
    "toan":  None,                 # ca anh, hai ben nen mo
    "mat":   (0.50, 0.30, 0.52),   # dau + vai nguoi dan
    "than":  (0.50, 0.48, 0.74),
    "trai":  (0.24, 0.44, 0.46),
    "phai":  (0.78, 0.46, 0.46),
    "tren":  (0.50, 0.24, 0.62),
    "duoi":  (0.50, 0.74, 0.62),
}

# Chuyen dong. "tinh" = DUNG YEN -- danh cho cu may vao nguoi dan: zoom vao mot
# nguoi chi dang doc loi binh thi vo nghia, va lam nguoi xem tuong sap co gi do.
CHUYEN_DONG = {
    "tinh":       ("1.0",                     "iw/2-(iw/zoom/2)",        "ih/2-(ih/zoom/2)"),
    "zoom_vao":   ("min(zoom+0.00030,1.12)",  "iw/2-(iw/zoom/2)",        "ih/2-(ih/zoom/2)"),
    "zoom_ra":    ("max(1.12-0.00030*on,1)",  "iw/2-(iw/zoom/2)",        "ih/2-(ih/zoom/2)"),
    "troi_phai":  ("1.10",                    "(iw-iw/zoom)*on/{N}",     "ih/2-(ih/zoom/2)"),
    "troi_trai":  ("1.10",                    "(iw-iw/zoom)*(1-on/{N})", "ih/2-(ih/zoom/2)"),
    "troi_len":   ("1.10",                    "iw/2-(iw/zoom/2)",        "(ih-ih/zoom)*(1-on/{N})"),
    "troi_xuong": ("1.10",                    "iw/2-(iw/zoom/2)",        "(ih-ih/zoom)*on/{N}"),
}

# Mau cat tu dong khi kich ban khong ghi ro. Cu may dau LUON la "toan/tinh":
# vao segment thi cho nguoi xem thay ca bo cuc truoc da, va dung yen.
_MAU_CAT = [
    ["trai", "phai", "tren", "duoi"],      # canh 1: sang trai truoc
    ["phai", "trai", "duoi", "tren"],      # canh 2: doi ben cho khong lap
]


def _cu_may_tu_dong(giay: float, thu_tu: int, la_nguoi_dan: bool) -> list[dict]:
    """Chia mot segment thanh may cu may, khi kich ban khong ghi ro.

    Duoi 4,5s thi mot cu -- cat nhanh hon nua la giat. Tren the thi 2-3 cu.
    Canh NGUOI DAN: cu dau dung yen o toan canh, cac cu sau cat sang chi tiet
    nen (ban do, may chieu, thung ho so) chu KHONG zoom vao mat nguoi dan.
    """
    if giay < 4.5:
        return [{"vung": "toan", "chuyen_dong": "tinh" if la_nguoi_dan else "zoom_vao"}]
    chi_tiet = _MAU_CAT[thu_tu % len(_MAU_CAT)]
    so_cu = 2 if giay < 8 else 3
    cu = [{"vung": "toan", "chuyen_dong": "tinh" if la_nguoi_dan else "zoom_vao"}]
    for i in range(so_cu - 1):
        cu.append({"vung": chi_tiet[i % len(chi_tiet)],
                   "chuyen_dong": ("troi_phai", "troi_trai", "zoom_vao")[i % 3]})
    return cu


def _loc_mot_cu(cu: dict, kb, khung: int, ti_anh: float) -> str:
    """Dung chuoi filter ffmpeg cho MOT cu may."""
    z, x, y = CHUYEN_DONG.get(cu.get("chuyen_dong", "tinh"), CHUYEN_DONG["tinh"])
    x, y = x.format(N=max(khung, 1)), y.format(N=max(khung, 1))
    vung = VUNG.get(cu.get("vung", "toan"), None)
    W2, H2 = kb.rong * 2, kb.cao * 2

    if vung is None:
        # Ca anh. Neu anh lech ti le khung qua 12% thi hai ben lap nen mo, khong
        # cat -- cat anh 1:1 vao khung 16:9 la mat 44% chieu cao.
        if abs(ti_anh - kb.rong / kb.cao) / (kb.rong / kb.cao) > 0.12:
            return (f"[0:v]scale={W2}:{H2}:force_original_aspect_ratio=increase,"
                    f"crop={W2}:{H2},gblur=sigma=32,eq=brightness=-0.20:saturation=0.7,"
                    f"scale={kb.rong}:{kb.cao},setsar=1[nen];"
                    f"[0:v]scale=-2:{kb.cao * 2},"
                    f"zoompan=z='{z}':x='{x}':y='{y}':d={khung}:"
                    f"s={int(kb.cao * ti_anh)}x{kb.cao}:fps={kb.fps},setsar=1[tc];"
                    f"[nen][tc]overlay=(W-w)/2:(H-h)/2,format=yuv420p")
        return (f"[0:v]scale={W2}:{H2}:force_original_aspect_ratio=increase,"
                f"crop={W2}:{H2},zoompan=z='{z}':x='{x}':y='{y}':d={khung}:"
                f"s={kb.rong}x{kb.cao}:fps={kb.fps},format=yuv420p")

    # Cat mot vung: cua so dung ti le khung ra, giu trong bien anh.
    cx, cy, rong = vung
    return (f"[0:v]scale={W2}:-2,"
            f"crop=w='min(iw*{rong},iw)':h='min(iw*{rong}*{kb.cao}/{kb.rong},ih)':"
            f"x='clip(iw*{cx}-ow/2,0,iw-ow)':y='clip(ih*{cy}-oh/2,0,ih-oh)',"
            f"zoompan=z='{z}':x='{x}':y='{y}':d={khung}:"
            f"s={kb.rong}x{kb.cao}:fps={kb.fps},format=yuv420p")


def lam_ken_burns(canh, kb, thu_tu: int) -> dict:
    """Anh tinh -> clip, bang ffmpeg. Khong dung GPU, khong sinh lai pixel nao.

    Khac Wan o cho co ban: Wan VE LAI tung khung hinh nen net ve goc bi troi
    (do duoc: nhan vat mat long may, mat tron hon, mat ao lot). Ken Burns giu
    NGUYEN anh cua Gemini, chi di chuyen cua so nhin -- nen net van sac nhu anh
    goc 2048px.

    Mot segment duoc chia thanh nhieu CU MAY roi noi lai, thay vi giu mot khung
    hinh suot 6-10 giay.
    """
    if canh.co_thoai:
        if not canh.duong_wav.exists():
            C.loi(f"{canh.id}: chua co {canh.duong_wav.name}. Chay buoc 1 truoc.")
        giay = C.do_dai_wav(canh.duong_wav)
    else:
        giay = kb.giay_canh_khong_thoai

    from PIL import Image
    with Image.open(canh.duong_anh) as im:
        ti_anh = im.size[0] / im.size[1]

    cu_may = canh.cu_may or _cu_may_tu_dong(giay, thu_tu, canh.nguoi_dan)
    tong_khung = max(2, int(round(giay * kb.fps)))
    # Chia khung cho tung cu, cu cuoi nhan phan du -> tong luon khop do dai tieng.
    moi_cu = max(1, tong_khung // len(cu_may))
    chia = [moi_cu] * len(cu_may)
    chia[-1] += tong_khung - moi_cu * len(cu_may)

    C.buoc(f"{canh.id}  [KEN BURNS]  {kb.rong}x{kb.cao}  {tong_khung} khung = "
           f"{tong_khung / kb.fps:.2f}s  ·  {len(cu_may)} cu may"
           f"{'  (canh NGUOI DAN)' if canh.nguoi_dan else ''}")
    C.CLIP.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    tam = []
    for i, (cu, k) in enumerate(zip(cu_may, chia)):
        ra = C.LOGS / f"_cu_{canh.id}_{i}.mp4"
        loc = _loc_mot_cu(cu, kb, k, ti_anh)
        C.noi(f"  cu {i + 1}: {cu.get('vung', 'toan')} · "
              f"{cu.get('chuyen_dong', 'tinh')} · {k / kb.fps:.2f}s")
        r = subprocess.run(
            [C.FFMPEG, "-y", "-v", "error", "-loop", "1", "-i", str(canh.duong_anh),
             "-filter_complex", loc, "-frames:v", str(k), "-r", str(kb.fps),
             "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", str(ra)], capture_output=True, text=True)
        if r.returncode:
            C.loi(f"ffmpeg loi o cu {i + 1} cua {canh.id}:\n{r.stderr[-1200:]}")
        tam.append(ra)

    ds = C.LOGS / f"_cu_{canh.id}.txt"
    ds.write_text("".join(f"file '{t}'\n" for t in tam), encoding="utf-8")
    lenh = [C.FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(ds)]
    if canh.co_thoai:
        lenh += ["-i", str(canh.duong_wav), "-map", "0:v", "-map", "1:a",
                 "-c:a", "aac", "-b:a", "192k", "-shortest"]
    lenh += ["-c:v", "copy", str(canh.duong_clip)]
    r = subprocess.run(lenh, capture_output=True, text=True)
    for t in tam:
        t.unlink(missing_ok=True)
    ds.unlink(missing_ok=True)
    if r.returncode:
        C.loi(f"ffmpeg loi khi noi cu may cua {canh.id}:\n{r.stderr[-1200:]}")

    giay_lam = time.time() - t0
    C.noi(f"-> {canh.duong_clip.relative_to(C.GOC)}  "
          f"{canh.duong_clip.stat().st_size / 1048576:.1f} MB  "
          f"{C.do_dai_wav(canh.duong_clip):.2f}s  (mat {giay_lam:.1f}s)")
    return {"id": canh.id, "loai": "KEN_BURNS", "khung": tong_khung,
            "giay_clip": round(tong_khung / kb.fps, 2), "giay_render": round(giay_lam, 1),
            "so_cu_may": len(cu_may), "nguoi_dan": canh.nguoi_dan,
            "cu_may": [f"{c.get('vung','toan')}/{c.get('chuyen_dong','tinh')}" for c in cu_may]}


# Ta mo ta nhan vat, gan y NGUYEN VAN vao moi prompt. LTX ve lai tung khung
# nen neu khong nhac lai dac diem thi moi canh no doan mot kieu -- dung cai bay
# da lam Wan hong (do duoc: canh 1 mat long may, canh 3 giu).
_TA_NHAN_VAT = ("flat vector cartoon narrator in a conical straw hat and pink floral shirt")

# Prompt AM cua ban cho ket qua tot nhat (ltx_tieng_cua_no.mp4). Hai chu
# "silent, music only" la CO CHU DICH: chung DAY model phai sinh ra LOI NOI
# thay vi nhac nen hay tieng dong. Bo chung di la tieng bien mat.
# Dung noi dai them tu chong nhieu -- ban dai hon da cho ket qua TE hon.
_LTX_AM = "blurry, distorted, silent, music only, watermark"


def dem_ve_khung(nguon: Path, dich: Path, rong: int, cao: int) -> bool:
    """Dem anh ve dung ti le khung ra, KHONG cat mat gi.

    Anh Gemini la 1:1; nhet thang vao khung 16:9 thi model cat mat 44% chieu
    cao -- do la ly do chiec non bien mat o dau clip. Hai ben lap bang chinh
    anh do phong to + lam mo. Tra ve True neu co dem.
    """
    from PIL import Image, ImageFilter
    with Image.open(nguon) as im:
        im = im.convert("RGB")
        if abs(im.width / im.height - rong / cao) / (rong / cao) <= 0.02:
            im.resize((rong, cao), Image.LANCZOS).save(dich)
            return False
        ti = max(rong / im.width, cao / im.height)
        nen = im.resize((int(im.width * ti) + 1, int(im.height * ti) + 1), Image.LANCZOS)
        x, y = (nen.width - rong) // 2, (nen.height - cao) // 2
        nen = nen.crop((x, y, x + rong, y + cao)).filter(ImageFilter.GaussianBlur(28))
        nen = Image.blend(nen, Image.new("RGB", (rong, cao), (12, 12, 14)), 0.28)
        ti2 = cao / im.height
        tc = im.resize((max(1, int(im.width * ti2)), cao), Image.LANCZOS)
        nen.paste(tc, ((rong - tc.width) // 2, 0))
        nen.save(dich)
        return True


def lam_ltx(canh, kb, seed: int) -> dict:
    """LTX-2.5 22B (NVFP4). Anh -> clip co chuyen dong that.

    Mot canh co the gom NHIEU CU MAY: moi cu la mot lan render rieng voi prompt
    rieng, xong noi lai. Kich ban khai o `cu_may`:
        "cu_may": [{"ta": "...", "phan": 2}, {"ta": "...", "phan": 1}]
    `phan` la trong so chia thoi luong; bo trong thi chia deu. Khong khai cu_may
    thi ca canh la mot cu, dung `ghi_chu`.

    LTX tu sinh CA tieng, nhung ta bo di va ghep tieng TTS cua minh vao -- nen
    KHONG co khop mieng. Doi lai: giu net ve goc va nhat quan giua cac canh.
    """
    vao_comfy = C.COMFY / "input"
    vao_comfy.mkdir(parents=True, exist_ok=True)
    ten_anh = f"{canh.id}_{uuid.uuid4().hex[:6]}.png"
    da_dem = dem_ve_khung(canh.duong_anh, vao_comfy / ten_anh, kb.rong, kb.cao)

    giay_tts = C.do_dai_wav(canh.duong_wav) if canh.co_thoai else 0.0
    giay = giay_tts
    # Kich ban co timecode (_giay_du_kien) thi canh phai CU DUNG YEN do dai:
    # dung dai tieng (canh co thoai) HAY timecode, kieu na SE NAY.
    # Neu khong co tieng thi dung timecode; neu hai do khong co thi dung
    # giay_canh_khong_thoai mac dinh.
    du_kien = canh.giay_du_kien or 0.0
    if canh.co_thoai:
        giay = max(giay_tts, du_kien)
    else:
        giay = max(du_kien, kb.giay_canh_khong_thoai)
    tong_khung = C.so_khung(giay, kb.fps, toi_da=401, buoc=8)

    cu_may = canh.cu_may or [{"ta": canh.ghi_chu}]
    trong = [max(1, int(c.get("phan", 1))) for c in cu_may]
    # chia khung theo trong so, moi cu van phai la 8n+1
    chia = []
    con = tong_khung
    for i, w in enumerate(trong):
        if i == len(trong) - 1:
            k = con
        else:
            k = C.so_khung(tong_khung * w / sum(trong) / kb.fps, kb.fps, toi_da=401, buoc=8)
            k = min(k, con - 9 * (len(trong) - i - 1))
        chia.append(max(9, k)); con -= chia[-1]

    C.buoc(f"{canh.id}  [LTX-2.5]  {kb.rong}x{kb.cao}  {tong_khung} khung = "
           f"{tong_khung / kb.fps:.2f}s @ {kb.fps}fps  ·  {len(cu_may)} cu may")
    if da_dem:
        C.noi("anh lech ti le -> da DEM ve 16:9 (khong cat mat phan nao)")
    if canh.co_thoai:
        C.noi(f"tieng dai {giay:.2f}s -> {tong_khung} khung (LTX doi 8n+1)")

    dovram = DoVram(C.gpu_dung()); dovram.start()
    t0 = time.time()
    tat_ca, tieng = [], []
    for i, (cu, k) in enumerate(zip(cu_may, chia)):
        ta = cu.get("ta") or canh.ghi_chu
        # LTX tu sinh tieng va khop mieng theo chinh tieng do. Nhet cau thoai
        # cua CU NAY vao prompt de no doc dung doan dang minh hoa -- neu dua ca
        # doan dai cho moi cu thi hai cu se doc trung nhau.
        loi = (cu.get("_loi") or "").strip() or (canh.thoai if len(cu_may) == 1 else "")
        if loi:
            ta = f'{ta}; he speaks to camera and says: "{loi}"'
        # Ba muc chat luong, doi ten file la doi muc:
        #   ltx25.json      distilled nvfp4 -- nhanh nhat, cfg=1 (khong guidance)
        #   ltx25_dev.json  dev int8        -- DANG DUNG: 30 steps, cfg 3.0/7.0
        #   ltx25_bf16.json dev bf16 39GB   -- 39GB > 32GB VRAM nen phai offload,
        #                                      cham hon int8 ma hon chat khong bao nhieu
        wf = nap_workflow("ltx25_dev.json")
        dat(wf, "20", "image", ten_anh)
        dat(wf, "30", "text", ta.strip())
        dat(wf, "31", "text", _LTX_AM)
        dat(wf, "32", "frame_rate", float(kb.fps))
        for kk, v in (("width", kb.rong), ("height", kb.cao), ("length", k)):
            dat(wf, "40", kk, v)
        dat(wf, "42", "frames_number", k)
        dat(wf, "42", "frame_rate", float(kb.fps))
        dat(wf, "51", "noise_seed", seed + i * 7919)   # moi cu mot hat khac
        dat(wf, "70", "filename_prefix", f"ltx/{canh.id}_{i}")
        dat(wf, "71", "filename_prefix", f"ltx/{canh.id}_{i}_am")

        C.noi(f"  cu {i + 1}/{len(cu_may)}: {k} khung = {k / kb.fps:.2f}s · {ta[:64]}")
        kq = goi("/prompt", {"prompt": wf, "client_id": f"ltx-{uuid.uuid4().hex[:8]}"})
        h = cho_xong(kq["prompt_id"], f"{canh.id} cu {i + 1}")
        ra = []
        for node in h.get("outputs", {}).values():
            for im in node.get("images", []):
                ra.append(C.COMFY / "output" / (im.get("subfolder") or "") / im["filename"])
            for au in node.get("audio", []):
                tieng.append(C.COMFY / "output" / (au.get("subfolder") or "") / au["filename"])
        ra = sorted(p for p in ra if p.exists())
        if not ra:
            C.loi(f"{canh.id} cu {i + 1}: khong ra khung nao.")
        tat_ca += ra

    giay_render = time.time() - t0
    dovram.chay = False
    C.noi(f"render xong {len(tat_ca)} khung sau {giay_render:.1f}s "
          f"({giay_render / max(len(tat_ca), 1):.2f}s/khung)")
    C.noi(f"VRAM: nen {dovram.nen_mib} + pipeline {dovram.rieng_mib} MiB")

    tieng = [p for p in tieng if p.exists()]
    # QUA LTX: KHONG dung tieng LTX tu sinh (mieng LTX no na voi khang khong
    # khop = tieng hanh thay vi bo di) -- dung tieng TTS cua kich ban de khoi
    # loi thoai that va co noi that. giay_ngan giu do dai video theo kich ban.
    C.noi(f"tieng LTX tu sinh: {len(tieng)} file (bo qua — dung TTS kich ban)")
    ghep_mp4(tat_ca, canh, kb, tieng_rieng=None, giay_ngan=giay)
    (vao_comfy / ten_anh).unlink(missing_ok=True)
    for p in tat_ca + tieng:
        p.unlink(missing_ok=True)
    return {"id": canh.id, "loai": "LTX", "khung": len(tat_ca), "so_cu_may": len(cu_may),
            "so_file_tieng": len(tieng), "giay_du_kien": round(giay, 2),
            "giay_clip": round(len(tat_ca) / kb.fps, 2), "giay_render": round(giay_render, 1),
            "giay_moi_khung": round(giay_render / max(len(tat_ca), 1), 2),
            "vram_pipeline_mib": dovram.rieng_mib}


# Phong cach mac dinh cho kieu "t2v" (tu ve) khi ghi_chu de trong: bang trang
# ke chuyen — lay tu chinh ban thu bang trang da dat (thu_bangtrang_full_20s).
_T2V_PHONG_CACH = (
    "continuous hand-drawn whiteboard animation on cream paper texture, "
    "black ink stick figures, handwritten cursive words floating around, "
    "taped newspaper clippings and index cards, the story plays across the "
    "page in one continuous flowing motion"
)


def _chia_khuc(tong_khung: int, cap: int = 241) -> list[int]:
    """Chia so khung thanh cac khuc <= cap, moi khuc deu la 8n+1 (doi hoi cua
    LTX latent). Khuc cuoi lam tron LEN len 8n+1 nen clip co the dai hon muc
    toi da 7 khung (0.3s) — ghep_mp4 van cat dung theo so khung thuc te."""

    def lon_nhat_8n1(n: int) -> int:
        # so 8n+1 nho nhat ma van >= n
        return max(9, ((n + 6) // 8) * 8 + 1)

    so_khuc = max(1, -(-tong_khung // cap))
    chia = []
    con = tong_khung
    for i in range(so_khuc):
        k = con if i == so_khuc - 1 else min(cap, con)
        k = lon_nhat_8n1(k)
        chia.append(k)
        con -= k
    return chia


def lam_t2v(canh, kb, seed: int) -> dict:
    """LTX-2.5 TEXT-TO-VIDEO — KHONG dung anh mau nhan vat.

    Day la "tu ve" that su: model doc prompt va VE RA TOAN BO canh tu con so
    khong (workflow ltx25_t2v.json, EmptyLTXVLatentVideo). Chinh cach nay da
    lam ra thu_bangtrang_full_20s.mp4.

    Prompt lay tu `ghi_chu`; de trong thi dung phong cach bang trang mac dinh
    ket hop loi thoai lam tiet xu cua canh. Tieng LTX tu sinh van bi BO — clip
    lay tieng TTS cua kich ban, do dai giu theo timecode giong kieu "ltx".

    Canh dai hon 241 khung (~10s @24fps) duoc chia nhieu khuc render rieng
    (cung prompt, khac hat seed) roi noi lai — LTX khong giu lien tuc giua cac
    khuc nen se co cu cat nhe o diem noi. Cap 241 khung la do chinh thuc
    nghiem tren may nay: dat dinh ~24.4GB VRAM — vua troi GPU0 khi nguoi dung
    khac dang chiem 7.2GB.
    """
    giay_tts = C.do_dai_wav(canh.duong_wav) if canh.co_thoai else 0.0
    du_kien = canh.giay_du_kien or 0.0
    if canh.co_thoai:
        giay = max(giay_tts, du_kien)
    else:
        giay = max(du_kien, kb.giay_canh_khong_thoai)
    tong_khung = C.so_khung(giay, kb.fps, toi_da=401, buoc=8)

    chia = _chia_khuc(tong_khung, cap=241)
    so_khuc = len(chia)

    ta = (canh.ghi_chu or "").strip()
    # Phong cach LUON ap dung cho moi canh — day la thu giu cac canh giong nhau.
    # Kich ban co the tu dat `cau_hinh.phong_cach_t2v` (go o giao dien) de doi
    # han nhan vat / net ve; de trong thi dung bang trang mac dinh.
    # ghi_chu chi la NOI DUNG tiet tau cua canh.
    phong_cach = (getattr(kb, "phong_cach_t2v", "") or "").strip() or _T2V_PHONG_CACH
    noi_dung = ta or canh.thoai.strip() or "the story begins"
    ta = f"{phong_cach}: {noi_dung}"

    C.buoc(f"{canh.id}  [T2V tu ve]  {kb.rong}x{kb.cao}  {tong_khung} khung = "
           f"{tong_khung / kb.fps:.2f}s @ {kb.fps}fps  ·  {so_khuc} khuc")
    if canh.co_thoai:
        C.noi(f"tieng TTS {giay_tts:.2f}s + timecode {du_kien:.0f}s -> giu {giay:.2f}s")
    C.noi(f"prompt: {ta[:90]}")

    dovram = DoVram(C.gpu_dung())
    dovram.start()
    t0 = time.time()
    tat_ca, tieng = [], []
    for i, k in enumerate(chia):
        # ltx25_t2v.json     = distilled nvfp4, 8 buoc ManualSigmas, cfg 1.0
        # ltx25_t2v_dev.json = DANG DUNG: dev int8, 30 buoc, cfg 3.0/7.0
        wf = nap_workflow("ltx25_t2v_dev.json")
        dat(wf, "30", "text", ta)
        dat(wf, "31", "text", _LTX_AM)
        dat(wf, "32", "frame_rate", float(kb.fps))
        for kk, v in (("width", kb.rong), ("height", kb.cao), ("length", k)):
            dat(wf, "40", kk, v)
        dat(wf, "42", "frames_number", k)
        dat(wf, "42", "frame_rate", float(kb.fps))
        dat(wf, "51", "noise_seed", seed + i * 7919)
        dat(wf, "70", "filename_prefix", f"ltx/{canh.id}_t2v_{i}")
        dat(wf, "71", "filename_prefix", f"ltx/{canh.id}_t2v_{i}_am")

        C.noi(f"  khuc {i + 1}/{so_khuc}: {k} khung = {k / kb.fps:.2f}s")
        kq = goi("/prompt", {"prompt": wf, "client_id": f"t2v-{uuid.uuid4().hex[:8]}"})
        h = cho_xong(kq["prompt_id"], f"{canh.id} khuc {i + 1}")
        ra = []
        for node in h.get("outputs", {}).values():
            for im in node.get("images", []):
                ra.append(C.COMFY / "output" / (im.get("subfolder") or "") / im["filename"])
            for au in node.get("audio", []):
                tieng.append(C.COMFY / "output" / (au.get("subfolder") or "") / au["filename"])
        ra = sorted(p for p in ra if p.exists())
        if not ra:
            C.loi(f"{canh.id} khuc {i + 1}: khong ra khung nao.")
        tat_ca += ra

    giay_render = time.time() - t0
    dovram.chay = False
    C.noi(f"render xong {len(tat_ca)} khung sau {giay_render:.1f}s "
          f"({giay_render / max(len(tat_ca), 1):.2f}s/khung)")
    C.noi(f"VRAM: nen {dovram.nen_mib} + pipeline {dovram.rieng_mib} MiB")

    tieng = [p for p in tieng if p.exists()]
    C.noi(f"tieng LTX tu sinh: {len(tieng)} file (bo qua — dung TTS kich ban)")
    ghep_mp4(tat_ca, canh, kb, tieng_rieng=None, giay_ngan=giay)
    for p in tat_ca + tieng:
        p.unlink(missing_ok=True)
    return {"id": canh.id, "loai": "T2V", "khung": len(tat_ca), "so_khuc": so_khuc,
            "giay_du_kien": round(giay, 2),
            "giay_clip": round(len(tat_ca) / kb.fps, 2), "giay_render": round(giay_render, 1),
            "giay_moi_khung": round(giay_render / max(len(tat_ca), 1), 2),
            "vram_pipeline_mib": dovram.rieng_mib}


def lam_mot_canh(canh, kb, buoc_lay: int, seed: int, cfg: float | None) -> dict:
    vao_comfy = C.COMFY / "input"
    vao_comfy.mkdir(parents=True, exist_ok=True)

    ten_anh = f"{canh.id}_{uuid.uuid4().hex[:6]}.png"
    shutil.copy(canh.duong_anh, vao_comfy / ten_anh)

    prefix = f"vhh/{canh.id}"
    if canh.kieu == "s2v":
        if not canh.duong_wav.exists():
            C.loi(f"{canh.id}: chua co {canh.duong_wav.name}. Chay buoc 1 truoc "
                  f"(python scripts/01_tts.py --canh {canh.id}).")
        ten_wav = f"{canh.id}_{uuid.uuid4().hex[:6]}.wav"
        shutil.copy(canh.duong_wav, vao_comfy / ten_wav)
        giay = C.do_dai_wav(canh.duong_wav)
        khung = C.so_khung(giay, kb.fps)

        wf = nap_workflow("s2v.json")
        dat(wf, "20", "image", ten_anh)
        dat(wf, "21", "audio", ten_wav)
        dat(wf, "30", "text", canh.ghi_chu or "cinematic animation, natural motion")
        dat(wf, "31", "text", C.NEGATIVE_MAC_DINH)
        for k, v in (("width", kb.rong), ("height", kb.cao), ("length", khung)):
            dat(wf, "40", k, v)
        dat(wf, "50", "seed", seed)
        dat(wf, "50", "steps", buoc_lay)
        if cfg is not None:
            dat(wf, "50", "cfg", cfg)
        dat(wf, "70", "filename_prefix", prefix)
        loai = "S2V"
    else:
        # I2V: neu canh CO loi doc (phim dan chuyen) thi do dai clip phai bam theo
        # tieng, khong lay so giay mac dinh — khong thi hinh va tieng lech nhau.
        if canh.co_thoai and canh.duong_wav.exists():
            giay = C.do_dai_wav(canh.duong_wav)
        else:
            giay = kb.giay_canh_khong_thoai
        khung = C.so_khung(giay, kb.fps)

        wf = nap_workflow("i2v.json")
        dat(wf, "20", "image", ten_anh)
        dat(wf, "30", "text", canh.ghi_chu or "cinematic camera movement, natural motion")
        dat(wf, "31", "text", C.NEGATIVE_MAC_DINH)
        for k, v in (("width", kb.rong), ("height", kb.cao), ("length", khung)):
            dat(wf, "40", k, v)
        for n in ("50", "51"):
            dat(wf, n, "noise_seed", seed)
            dat(wf, n, "steps", buoc_lay)
            if cfg is not None:
                dat(wf, n, "cfg", cfg)
        dat(wf, "50", "end_at_step", buoc_lay // 2)
        dat(wf, "51", "start_at_step", buoc_lay // 2)
        dat(wf, "70", "filename_prefix", prefix)
        loai = "I2V"

    C.buoc(f"{canh.id}  [{loai}]  {kb.rong}x{kb.cao}  {khung} khung "
           f"= {khung / kb.fps:.2f}s @ {kb.fps}fps  ({buoc_lay} buoc lay mau)")
    if canh.co_thoai and canh.duong_wav.exists():
        C.noi(f"tieng dai {giay:.2f}s -> lam tron len {khung} khung (Wan doi dang 4n+1)")

    dovram = DoVram(C.gpu_dung())
    dovram.start()
    t0 = time.time()
    kq = goi("/prompt", {"prompt": wf, "client_id": f"vhh-{uuid.uuid4().hex[:8]}"})
    h = cho_xong(kq["prompt_id"], canh.id)
    giay_render = time.time() - t0
    dovram.chay = False

    anh_ra = []
    for node in h.get("outputs", {}).values():
        for im in node.get("images", []):
            anh_ra.append(C.COMFY / "output" / (im.get("subfolder") or "") / im["filename"])
    anh_ra = sorted(p for p in anh_ra if p.exists())
    if not anh_ra:
        C.loi(f"{canh.id}: ComfyUI chay xong nhung khong ra khung hinh nao.")
    C.noi(f"render xong {len(anh_ra)} khung sau {giay_render:.1f}s "
          f"({giay_render / max(khung, 1):.2f}s/khung)")
    C.noi(f"VRAM: nen {dovram.nen_mib} MiB (viec khac) + pipeline {dovram.rieng_mib} MiB "
          f"= dinh {dovram.dinh_mib} MiB")

    ghep_mp4(anh_ra, canh, kb)
    for p in (vao_comfy / ten_anh,):
        p.unlink(missing_ok=True)
    if canh.co_thoai:
        (vao_comfy / ten_wav).unlink(missing_ok=True)
    for p in anh_ra:
        p.unlink(missing_ok=True)

    return {"id": canh.id, "loai": loai, "khung": khung,
            "giay_clip": round(khung / kb.fps, 2),
            "giay_render": round(giay_render, 1),
            "giay_moi_khung": round(giay_render / max(khung, 1), 2),
            "vram_dinh_mib": dovram.dinh_mib, "vram_nen_mib": dovram.nen_mib,
            "vram_pipeline_mib": dovram.rieng_mib, "buoc_lay": buoc_lay}


def ghep_mp4(khung: list[Path], canh, kb, tieng_rieng: list[Path] | None = None,
             giay_ngan: float | None = None) -> None:
    """Ghep day PNG + wav thanh mp4.

    `tieng_rieng`  = tieng do CHINH MODEL sinh (khop mieng) — dung QUA Wan S2V.
    `giay_ngan`    = do dai MUC cua canh (kieu LTX). Neu canh co thoai thi ghep
                     tieng TTS cua kich ban len hinh, va `apad` them IAM TIEU
                     (silence) cho khong canh co tieng ngang hon duoc CAI do dai
                     video thang giay_ngan. Khong dung `-shortest` de cat NGHI
                     do dai kich ban.

    Tu mux bang ffmpeg thay vi dung node SaveVideo cua ComfyUI: schema
    DynamicCombo cua node do hay doi, con o day ta giu ma hoa dong nhat
    giua moi canh de buoc 3 noi lai khong phai ma hoa lai.

    Dung image2 demuxer (so thu tu 00001, 00002, ...) thay vi concat demuxer:
    concat doc PNG bi LOI timebase (DTS/PTS invalid -> sot khung, clip ngan hon
    kich ban). Image2 giu NGUYEN so khung.
    """
    C.CLIP.mkdir(parents=True, exist_ok=True)
    # Day khung vao thu muc tam, dat ten 00001.png, 00002.png, ... de image2
    # demuxer doc dung thu tu. Khung da xoa sau khi ghep xong.
    tam = C.LOGS / f"_khung_{canh.id}"
    tam.mkdir(parents=True, exist_ok=True)
    for i, p in enumerate(khung, 1):
        dich = tam / f"{i:05d}.png"
        if p != dich:
            p.replace(dich)

    # Tieng: QUA S2V dung tieng do CHINH MODEL sinh (khop mieng). Kieu khac
    # thi dung tieng TTS cua kich ban (loi thoai that). Kieu LTX KHONG dung
    # tieng LTX tu sinh (mieng no na noi khang hinh khong khop) -- dung TTS.
    wav = None
    if tieng_rieng:
        if len(tieng_rieng) == 1:
            wav = tieng_rieng[0]
        else:
            dsa = C.LOGS / f"_tieng_{canh.id}.txt"
            dsa.write_text("".join(f"file '{p}'\n" for p in tieng_rieng), encoding="utf-8")
            wav = C.LOGS / f"_tieng_{canh.id}.wav"
            subprocess.run([C.FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0",
                            "-i", str(dsa), "-c:a", "pcm_s16le", str(wav)],
                           capture_output=True, text=True)
            dsa.unlink(missing_ok=True)
    elif canh.co_thoai:
        wav = canh.duong_wav

    lenh = [C.FFMPEG, "-y", "-framerate", str(kb.fps), "-start_number", "1",
            "-i", str(tam / "%05d.png")]
    if wav:
        lenh += ["-i", str(wav)]
    lenh += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p", "-r", str(kb.fps)]
    if wav:
        lenh += ["-c:a", "aac", "-b:a", "192k"]
        if giay_ngan is not None:
            # Canh LTX: cat dung bang do dai VIDEO (so khung / fps) bang `-t`,
            # KHONG dung `-shortest`. `-shortest` + `apad` van lech: AAC lam tron
            # khung nen audio dai hon video 0,04s, format duration theo audio ->
            # buoc 3 tinh offset xfade vuot video that, cat mat duoi clip.
            # `-t` cat ca hai stream dung bang do dai video, apad bom im lang
            # cho audio toi do.
            lenh += ["-af", "apad", "-t", f"{len(khung) / kb.fps:.6f}"]
        else:
            lenh += ["-shortest"]
    lenh += [str(canh.duong_clip)]

    r = subprocess.run(lenh, capture_output=True, text=True)
    for p in tam.glob("*.png"):
        p.unlink(missing_ok=True)
    tam.rmdir()
    if r.returncode:
        C.loi(f"ffmpeg loi khi ghep {canh.id}:\n{r.stderr[-1200:]}")
    C.noi(f"-> {canh.duong_clip.relative_to(C.GOC)}  "
          f"{canh.duong_clip.stat().st_size / 1048576:.1f} MB  "
          f"{C.do_dai_wav(canh.duong_clip):.2f}s")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--canh")
    p.add_argument("--lam-lai", action="store_true")
    p.add_argument("--buoc-lay", type=int, default=20)
    p.add_argument("--seed", type=int, default=1234)
    p.add_argument("--cfg", type=float)
    p.add_argument("--rong", type=int, help="de do A/B, khong sua kich ban")
    p.add_argument("--cao", type=int)
    p.add_argument("--kich-ban", help="dung file kich ban khac vao/kich_ban.json")
    p.add_argument("--do")
    a = p.parse_args()

    kb = C.doc_kich_ban(Path(a.kich_ban) if a.kich_ban else None)
    if a.rong:
        kb.rong = a.rong
    if a.cao:
        kb.cao = a.cao
    van_de = C.kiem_kich_ban(kb)
    if van_de:
        C.loi("Kich ban co van de:\n  - " + "\n  - ".join(van_de))

    canh = kb.canh
    if a.canh:
        canh = [c for c in canh if c.id == a.canh] or C.loi(f"Khong co canh '{a.canh}'")
    if not a.lam_lai:
        canh = [c for c in canh if not c.duong_clip.exists()]
    if not canh:
        C.noi("Moi canh da co clip. Them --lam-lai neu muon lam lai.")
        return

    can_gpu = [c for c in canh if c.kieu in ("i2v", "s2v", "ltx", "t2v")]
    if can_gpu:
        bat_comfy()
    else:
        C.noi("Khong canh nao can Wan -> khong bat ComfyUI.")
    C.buoc(f"Se lam {len(canh)} canh "
           f"({len(canh) - len(can_gpu)} Ken Burns, {len(can_gpu)} qua Wan)")
    do = {"buoc": "hoat_hinh", "gpu": C.gpu_dung(), "canh": []}
    t0 = time.time()
    for i, c in enumerate(canh):
        if c.kieu == "ken_burns":
            do["canh"].append(lam_ken_burns(c, kb, i))
        elif c.kieu == "ltx":
            do["canh"].append(lam_ltx(c, kb, a.seed))
        elif c.kieu == "t2v":
            do["canh"].append(lam_t2v(c, kb, a.seed))
        else:
            do["canh"].append(lam_mot_canh(c, kb, a.buoc_lay, a.seed, a.cfg))
    do["giay_tong"] = round(time.time() - t0, 1)
    C.buoc(f"XONG buoc hoat hinh sau {do['giay_tong']}s")
    if a.do:
        Path(a.do).write_text(json.dumps(do, ensure_ascii=False, indent=2), encoding="utf-8")
        C.noi(f"so do ghi vao {a.do}")


if __name__ == "__main__":
    main()
