"""Chay mot DU AN video tu dau toi cuoi: render tung canh -> ve chu -> tu dat chu -> dung video.

Du an la mot file JSON (giao dien tao ra, hoac viet tay):
  {"tieu_de", "phong_cach", "nhan_vat", "anh_mau", "bam_anh", "nhac", "seed",
   "canh": [{"prompt", "giay", "co_nhan_vat", "chu": [{"noi_dung", "kieu"}]}]}

  python cong_cu/du_an.py ra/du_an/<id>/du_an.json

Chay lai giua chung (tat may, loi mang...) thi canh nao da render ma prompt KHONG doi duoc
giu nguyen, chi render canh moi hoac canh da sua. Tien do ghi ra <du an>/tien_do.json cho
giao dien doc.
"""
from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import chu_collage as CC          # noqa: E402
import lam_video_collage as LV    # noqa: E402
import nhan_giay as NG            # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402

MAY = "http://127.0.0.1:8188"
COMFY = GOC / "ComfyUI"
WF = GOC / "workflows"
PHONG = GOC / "cong_cu" / "phong"
W, H, FPS = LV.W, LV.H, LV.FPS
RW, RH = 1280, 704                 # LTX doi boi so cua 32
AM = ("blurry, distorted, low quality, watermark, text, letters, film strip border, "
      "underexposed, too dark, black screen, letterbox bars")

# Caveat / Kalam / Special Elite THIEU dau tieng Viet (do bang fontTools: thieu 34-39 ky tu
# nhu ơ ư ạ ấ ệ -> ve ra o vuong). Moi dong chu lay font DAU TIEN trong danh sach phu du
# moi ky tu cua dong do; bang ky tu lap san o cong_cu/phong/bang_chu.json.
FONT = {
    "tay": ["Caveat.ttf", "PatrickHand-Regular.ttf", "Mali-SemiBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"],
    "may": ["SpecialElite-Regular.ttf", "CourierPrime-Bold.ttf", "IBMPlexMono-SemiBold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"],
}
_BANG: dict[str, set[int]] | None = None


def font_cho(vai: str, chu: str) -> Path:
    global _BANG
    if _BANG is None:
        p = PHONG / "bang_chu.json"
        _BANG = {k: set(v) for k, v in json.loads(p.read_text()).items()} if p.exists() else {}
    can = {ord(ch) for ch in chu if not ch.isspace()}
    co = []
    for ten in FONT[vai]:
        duong = Path(ten) if ten.startswith("/") else PHONG / ten
        if not duong.exists():
            continue
        co.append(duong)
        bang = _BANG.get(ten)
        if (bang is None and not _BANG) or (bang is not None and can <= bang):
            return duong
    if not co:
        raise RuntimeError(f"Khong co font nao cho vai '{vai}'")
    return co[-1]


# ----------------------------------------------------------------------- ComfyUI

def goi(duong: str, data: dict | None = None, timeout: int = 60) -> dict:
    req = urllib.request.Request(MAY + duong, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def dam_bao_comfy() -> None:
    try:
        goi("/system_stats", timeout=3)
        return
    except Exception:
        pass
    print("[du_an] ComfyUI chua chay -> bat", flush=True)
    subprocess.run(["bash", str(GOC / "cong_cu" / "comfy.sh"), "len"], check=True)


def so_khung(giay: float) -> int:
    """So khung 8n+1 >= giay*24 + 2 (du 2 khung de cat tia khong bi hut)."""
    return max(9, math.ceil((giay * FPS + 1) / 8) * 8 + 1)


def dem_16_9(nguon: Path, dich: Path) -> None:
    """Anh mau ve dung 1280x704, KHONG cat mat gi: phan thieu lap bang chinh anh phong to lam mo."""
    with Image.open(nguon) as im:
        im = im.convert("RGB")
        nen = im.resize((RW, RH), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
        tl = min(RW / im.width, RH / im.height)
        nho = im.resize((round(im.width * tl), round(im.height * tl)), Image.LANCZOS)
        nen.paste(nho, ((RW - nho.width) // 2, (RH - nho.height) // 2))
        nen.save(dich)


UNET_CUOI = GOC / "logs" / "comfy_unet.txt"          # model ve cua lan gui truoc


def _doi_model(wf: dict) -> None:
    """ComfyUI nap model moi van GIU model cu trong RAM: dev 21,5 GB + distilled 18,7 GB + Gemma 15 GB
    -> tran 60 GB. Doi model (Chuan <-> Nhanh) thi goi /free truoc; do duoc RSS 41 GB -> 4,5 GB sau ~10 s."""
    unet = (wf.get("10") or {}).get("inputs", {}).get("unet_name")
    if not unet:
        return
    cu = UNET_CUOI.read_text().strip() if UNET_CUOI.exists() else ""
    if cu and cu != unet:
        print(f"[du_an] doi model {cu} -> {unet}: giai phong ComfyUI truoc", flush=True)
        try:
            goi("/free", {"unload_models": True, "free_memory": True})
        except ValueError:
            pass                                          # /free tra ve than rong
        for _ in range(40):                               # doi giai phong XONG roi moi gui prompt moi
            time.sleep(1)
            try:
                d = goi("/system_stats", timeout=5)["devices"][0]
                if d["vram_free"] > 0.85 * d["vram_total"]:
                    break
            except Exception:
                pass
    UNET_CUOI.write_text(unet)


def _log_comfy() -> Path:
    """Log cua CHINH ComfyUI dang goi (comfy.sh: :8188 -> comfy.log, cong khac -> comfy_<cong>.log)."""
    cong = MAY.rsplit(":", 1)[-1]
    return GOC / "logs" / ("comfy.log" if cong == "8188" else f"comfy_{cong}.log")


def _so_buoc(wf: dict) -> list[int]:
    """So buoc cua tung luot lay mau theo thu tu (1 tang: [30] hoac [8]; 2 tang: [8, 3])."""
    ra = []
    for n in wf.values():
        if n.get("class_type") != "SamplerCustomAdvanced":
            continue
        s = wf.get(str(n["inputs"]["sigmas"][0]), {})
        if s.get("class_type") == "ManualSigmas":
            ra.append(max(1, len([x for x in str(s["inputs"]["sigmas"]).split(",") if x.strip()]) - 1))
        elif "steps" in s.get("inputs", {}):
            ra.append(int(s["inputs"]["steps"]))
    return ra or [1]


class _TheoTienDo:
    """Doc thanh tqdm ComfyUI in ra log ("4/8 [00:39<00:39,  9.80s/it]") tu luc gui prompt -> phan tram that.
    Chi dem dong co tong buoc khop workflow nen luot Gemma viet prompt chen vao cung ComfyUI khong lam sai."""

    def __init__(self, wf: dict) -> None:
        self.log = _log_comfy()
        self.moc = self.log.stat().st_size if self.log.exists() else 0
        self.buoc = _so_buoc(wf)
        self.pt = 0.0

    def doc(self, t0: float) -> tuple[str, float, float | None]:
        import re
        try:
            co = self.log.stat().st_size
            if co < self.moc:            # ComfyUI khoi dong lai, log bi ghi moi
                self.moc = 0
            with open(self.log, "rb") as f:
                f.seek(self.moc)
                moi = f.read(4_000_000).decode("utf-8", "replace")
        except Exception:
            moi = ""
        hop_le = set(self.buoc)
        luot, truoc = [], None         # moi luot: [so buoc da xong, tong]
        for k, n, toc in re.findall(r"(\d+)/(\d+) \[[^\]]*?(?:([\d.]+)s/it)?\]", moi):
            k, n = int(k), int(n)
            if n not in hop_le:
                continue
            if not luot or k < luot[-1][0] or n != luot[-1][1] or (luot[-1][0] == n and k < n):
                luot.append([k, n])
            luot[-1][0] = max(luot[-1][0], k)
            if toc:
                truoc = float(toc)
        tong = sum(self.buoc)
        xong = min(tong, sum(min(k, n) for k, n in luot))
        if not luot:
            pha, pt = "Đang nạp model và đọc prompt", min(8.0, (time.time() - t0) / 60 * 8)
        elif xong < tong:
            tang = f" · tầng {min(len(luot), len(self.buoc))}/{len(self.buoc)}" if len(self.buoc) > 1 else ""
            pha, pt = f"Đang vẽ{tang} · bước {xong}/{tong}", 8 + 80 * xong / tong
        else:
            pha, pt = "Đang giải mã video", 90.0
        self.pt = max(self.pt, pt)
        con_lai = (tong - xong) * truoc + 15 if truoc and xong < tong else None
        return pha, self.pt, con_lai


def chay_wf(wf: dict, ra: Path, ten: str, tien_do=None) -> float:
    """Gui mot workflow API toi ComfyUI, doi xong, dong goi cac khung SaveImage thanh mp4.

    Tra ve so giay ComfyUI chay (tu luc gui toi luc xong, khong tinh dong goi mp4).
    tien_do(pha, phan_tram 0-100, giay_con_lai | None): goi moi 2 giay de hien thanh tien trinh.
    """
    _doi_model(wf)
    t0 = time.time()
    theo = _TheoTienDo(wf) if tien_do else None
    pid = goi("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex})["prompt_id"]
    while True:
        time.sleep(2)
        if theo:
            try:
                tien_do(*theo.doc(t0))
            except Exception:
                pass
        h = goi(f"/history/{pid}").get(pid)
        if not h:
            continue
        tt = h.get("status", {})
        if tt.get("status_str") == "error":
            loi = [m for m in tt.get("messages", []) if m[0] == "execution_error"]
            raise RuntimeError(f"ComfyUI loi khi ve {ten}: " + json.dumps(loi, ensure_ascii=False)[:500])
        if tt.get("completed"):
            break
    giay = time.time() - t0
    if tien_do:
        tien_do("Đang đóng gói video", 96.0, 10)
    anh = sorted(COMFY / "output" / (im.get("subfolder") or "") / im["filename"]
                 for n in h["outputs"].values() for im in n.get("images", []))
    if not anh:
        raise RuntimeError(f"{ten}: ComfyUI khong ra khung nao")
    for n in h["outputs"].values():
        for au in n.get("audio", []):
            (COMFY / "output" / (au.get("subfolder") or "") / au["filename"]).unlink(missing_ok=True)
    ra.parent.mkdir(parents=True, exist_ok=True)
    tm = ra.parent / f".tam_{ra.stem}"
    shutil.rmtree(tm, ignore_errors=True)
    tm.mkdir()
    for j, p in enumerate(anh):
        shutil.move(str(p), tm / f"{j:05d}.png")
    LV.chay([LV.FF, "-v", "error", "-y", "-framerate", str(FPS), "-i", str(tm / "%05d.png"),
             "-c:v", "libx264", "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(ra)])
    shutil.rmtree(tm, ignore_errors=True)
    return giay


# Che do ve. So do cong_cu/do_toc_do.py, cung canh 1280x704 x 121 khung, RTX 5090 (xem README):
#   chuan : dev int8, 30 buoc, CFG 3/7 (co prompt am)                       272 s
#   nhanh : distilled nvfp4, 2 tang (8 buoc 640x352 -> phong x2 -> 3 buoc)    58 s, net hon o 100%
#           cfg 1 nen prompt am KHONG tac dung.
#   Da loai: EasyCache/LazyCache (khong bot duoc giay nao), dev 20 buoc (lam tam),
#            dev 2 tang (van luoi — bo phong latent can tang 2 cua model distilled).
CHE_DO = ("chuan", "nhanh")
UNET_CHUAN = "ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors"
UNET_NHANH = "ltx-2.5-22b-distilled-transformer-nvfp4.safetensors"
SIGMAS_DISTILLED = "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"
SIGMAS_TANG_2 = "0.85, 0.7250, 0.4219, 0.0"
SAMPLER_TANG_2 = "euler_ancestral"


def them_tang_2(wf: dict, hat: int, i2v: bool) -> dict:
    """Doi workflow 1 tang thanh 2 tang (nhu ti2vid_two_stages cua LTX-2): tang 1 ve o NUA do phan giai,
    phong latent x2 bang spatial upscaler, tang 2 tinh chinh o do phan giai day du tu sigma 0.85.
    i2v: gan lai anh vao latent da phong (strength 1) nhu workflow chinh thuc, khong thi khung dau troi."""
    v = wf["40"]["inputs"]
    v.update(width=v["width"] // 2, height=v["height"] // 2)          # 1280x704 -> 640x352 (van chia het 32)
    wf["100"] = {"class_type": "LatentUpscaleModelLoader",
                 "inputs": {"model_name": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"}}
    wf["101"] = {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["60", 0], "upscale_model": ["100", 0], "vae": ["12", 0]}}
    lat = ["101", 0]
    if i2v:
        wf["108"] = {"class_type": "LTXVImgToVideoInplace",
                     "inputs": {"vae": ["12", 0], "image": ["21", 0], "latent": lat, "strength": 1.0, "bypass": False}}
        lat = ["108", 0]
    wf["102"] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": lat, "audio_latent": ["60", 1]}}
    wf["103"] = {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS_TANG_2}}
    wf["104"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": hat + 1}}
    wf["107"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": SAMPLER_TANG_2}}
    wf["105"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["104", 0], "guider": ["50", 0], "sampler": ["107", 0],
                                                                   "sigmas": ["103", 0], "latent_image": ["102", 0]}}
    wf["106"] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["105", 0]}}
    wf["61"]["inputs"]["samples"] = ["106", 0]
    return wf


def wf_ve(prompt: str, k: int, hat: int, anh_comfy: str | None, ten: str, che_do: str = "chuan") -> dict:
    """Workflow API ve mot clip 1280x704. anh_comfy (ten file trong ComfyUI/input) -> i2v."""
    wf = json.loads((WF / ("ltx25_dev.json" if anh_comfy else "ltx25_t2v_dev.json")).read_text(encoding="utf-8"))
    wf["30"]["inputs"]["text"] = prompt
    wf["31"]["inputs"]["text"] = AM
    wf["32"]["inputs"]["frame_rate"] = float(FPS)
    wf["40"]["inputs"].update(width=RW, height=RH, length=k)
    wf["42"]["inputs"].update(frames_number=k, frame_rate=float(FPS))
    wf["51"]["inputs"]["noise_seed"] = hat
    wf["70"]["inputs"]["filename_prefix"] = ten
    wf["71"]["inputs"]["filename_prefix"] = ten + "_am"
    if anh_comfy:
        if not (COMFY / "input" / "giong_chuan.wav").exists():
            raise RuntimeError("Thieu ComfyUI/input/giong_chuan.wav (workflow i2v can)")
        wf["20"]["inputs"]["image"] = anh_comfy
    if che_do == "nhanh":         # nhu workflow chinh thuc LTX-2.5_T2V_I2V_Two_Stage_Distilled
        wf["10"]["inputs"]["unet_name"] = UNET_NHANH
        g = wf["50"]["inputs"]      # i2v: model/positive/negative da qua LTXVReferenceAudio (node 26)
        wf["50"] = {"class_type": "CFGGuider", "inputs": {"model": g["model"], "positive": g["positive"],
                                                          "negative": g["negative"], "cfg": 1.0}}
        wf["53"] = {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS_DISTILLED}}
        them_tang_2(wf, hat, bool(anh_comfy))
    return wf


# Giu nhan vat bang IC-LoRA Ingredients (thu 11/09/2026 cong_cu/thu_ingredients.py): chi on dinh khi ve DUNG
# bucket huan luyen 768x448 bang model distilled 1 tang. Ve 640x352 (2 tang) thi co canh CHEP NGUYEN bang
# tham chieu vao video; khong LoRA thi moi canh ra mot nguoi khac. Merge tu phong len 1280x720.
LORA_THAM_CHIEU = "ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors"
TC_W, TC_H = 768, 448
AM_THAM_CHIEU = "worst quality, inconsistent motion, blurry, jittery, distorted"


def wf_tham_chieu(prompt: str, k: int, hat: int, bang_comfy: str, ten: str) -> dict:
    """prompt dang 'Reference sheet: <ta tung o> Generated video: <canh>'; bang_comfy: file bang trong ComfyUI/input.
    Bang lap thanh video tinh DUNG BANG so khung video. Model card noi ">= 121 khung" nhung LTXVAddGuide bao
    loi "Conditioning frames exceed the length of the latent sequence" khi guide dai hon video (canh loi doc
    4 giay = 105 khung, kiem thu 11/09)."""
    wf = wf_ve(prompt, k, hat, None, ten)
    wf["40"]["inputs"].update(width=TC_W, height=TC_H)
    wf["31"]["inputs"]["text"] = AM_THAM_CHIEU
    wf["10"]["inputs"]["unet_name"] = UNET_NHANH
    wf["110"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["10", 0], "lora_name": LORA_THAM_CHIEU,
                                                                 "strength_model": 1.0}}
    wf["111"] = {"class_type": "GetICLoRAParameters", "inputs": {"iclora_model": ["110", 0]}}
    wf["112"] = {"class_type": "LoadImage", "inputs": {"image": bang_comfy}}
    wf["113"] = {"class_type": "RepeatImageBatch", "inputs": {"image": ["112", 0], "amount": k}}
    wf["114"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": ["32", 0], "negative": ["32", 1], "vae": ["12", 0],
                                                         "latent": ["40", 0], "image": ["113", 0], "frame_idx": 0,
                                                         "strength": 1.0, "iclora_parameters": ["111", 0]}}
    wf["43"]["inputs"]["video_latent"] = ["114", 2]
    wf["50"] = {"class_type": "CFGGuider", "inputs": {"model": ["110", 0], "positive": ["114", 0],
                                                      "negative": ["114", 1], "cfg": 1.0}}
    wf["52"]["inputs"]["sampler_name"] = "euler_ancestral_cfg_pp"      # nhu workflow chinh thuc
    wf["53"] = {"class_type": "ManualSigmas", "inputs": {"sigmas": SIGMAS_DISTILLED}}
    wf["115"] = {"class_type": "LTXVCropGuides", "inputs": {"positive": ["114", 0], "negative": ["114", 1],
                                                           "latent": ["60", 0]}}
    wf["61"]["inputs"]["samples"] = ["115", 2]                          # chi giai ma phan video that
    # Tang 2: phong latent x2 -> 1536x896, lam net tu sigma 0.42 bang model distilled TRON voi conditioning da cat
    # guide. So 11/09: net hon ro (vien, hoa van ao, van non) ma nhan dang y het; 146 s thay vi 95 s / 121 khung.
    # Tang 2 tu sigma 0.85 (nhu che do Nhanh) thi ve lai chi tiet -> mat mat nhan vat.
    v = wf["40"]["inputs"]
    v.update(width=2 * TC_W, height=2 * TC_H)
    them_tang_2(wf, hat, False)                                         # 40 -> 768x448 lai, them 100..107
    wf["103"]["inputs"]["sigmas"] = "0.4219, 0.2, 0.0"
    wf["101"]["inputs"]["samples"] = ["115", 2]
    wf["116"] = {"class_type": "CFGGuider", "inputs": {"model": ["10", 0], "positive": ["115", 0],
                                                       "negative": ["115", 1], "cfg": 1.0}}
    wf["105"]["inputs"]["guider"] = ["116", 0]
    return wf


def ve_tham_chieu(prompt: str, k: int, hat: int, bang: Path, ra: Path, ten: str, tien_do=None) -> None:
    tien_to = f"{ten}_{uuid.uuid4().hex[:6]}"
    anh_vao = COMFY / "input" / f"{Path(tien_to).name}_bang.png"
    shutil.copy(bang, anh_vao)
    try:
        chay_wf(wf_tham_chieu(prompt, k, hat, anh_vao.name, tien_to), ra, tien_to, tien_do)
    finally:
        anh_vao.unlink(missing_ok=True)


def ve_mot_clip(prompt: str, k: int, hat: int, anh_khung: Path | None, ra: Path, ten: str,
                che_do: str = "chuan", tien_do=None) -> None:
    """Mot lan ve LTX-2.5 qua ComfyUI -> mp4. anh_khung khac None thi i2v (anh lam khung mo dau).

    Dung chung cho luong ke chuyen (render_canh) va Xuong video (xuong.py).
    """
    tien_to = f"{ten}_{uuid.uuid4().hex[:6]}"
    anh_vao = None
    if anh_khung:
        anh_vao = COMFY / "input" / f"{Path(tien_to).name}.png"
        dem_16_9(anh_khung, anh_vao)
    try:
        chay_wf(wf_ve(prompt, k, hat, anh_vao.name if anh_vao else None, tien_to, che_do), ra, tien_to, tien_do)
    finally:
        if anh_vao:
            anh_vao.unlink(missing_ok=True)


def render_canh(i: int, c: dict, da: dict, D: Path) -> tuple[Path, bool]:
    """Render mot canh -> <du an>/clip/cNN.mp4. Tra ve (duong, da_giu_ban_cu)."""
    ra = D / "clip" / f"c{i + 1:02d}.mp4"
    ra.parent.mkdir(parents=True, exist_ok=True)
    dung_anh = bool(c.get("co_nhan_vat") and da.get("bam_anh") and da.get("anh_mau"))
    than = c["prompt"].strip()
    if c.get("co_nhan_vat") and da.get("nhan_vat"):
        than = f"{da['nhan_vat'].strip().rstrip('.')}. {than}"
    pc = (da.get("phong_cach") or "").strip()
    prompt = f"{pc}: {than}" if pc else than
    k = so_khung(float(c["giay"]))
    hat = int(da.get("seed", 1234)) + i * 7919

    dau = hashlib.sha1(json.dumps([prompt, k, dung_anh, hat, da.get("anh_mau") if dung_anh else ""],
                                  ensure_ascii=False).encode()).hexdigest()[:12]
    the = ra.with_suffix(".json")
    if ra.exists() and the.exists() and json.loads(the.read_text()).get("dau") == dau:
        return ra, True

    t0 = time.time()
    ve_mot_clip(prompt, k, hat, D / da["anh_mau"] if dung_anh else None, ra, f"du_an/{D.name}_c{i + 1:02d}")
    the.write_text(json.dumps({"dau": dau, "prompt": prompt, "khung": k, "anh_mau": dung_anh,
                               "giay_render": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1))
    return ra, False


# ------------------------------------------------------------------------- chu

def chia_dong(s: str, toi_da: int) -> list[str]:
    dong, hang = [], ""
    for t in s.split():
        if hang and len(hang) + 1 + len(t) > toi_da:
            dong.append(hang)
            hang = t
        else:
            hang = f"{hang} {t}".strip()
    if hang:
        dong.append(hang)
    return dong[:3]


def ve_chu(i: int, c: dict, D: Path) -> list[Path]:
    ra = []
    for k, ch in enumerate(c.get("chu") or []):
        nd = str(ch.get("noi_dung", "")).strip()
        if not nd:
            continue
        kieu, hat = ch.get("kieu", "nhan"), (i + 1) * 13 + k
        if kieu == "o_chu":
            tu = nd.upper().replace(" ", "")[:12]
            im = CC.o_chu(tu, co=86, hat=hat, font=font_cho("may", tu))
        elif kieu == "tieu_de":
            im = NG.nhan(nd.upper(), co=44, nghieng=-1.5, hat=hat, font=font_cho("may", nd.upper()))
        elif kieu == "viet":
            im = CC.tren_giay(NG.viet(chia_dong(nd, 22), co=60, nghieng=0, font=font_cho("tay", nd)),
                              hat=hat, le=26, nghieng=-2)
        else:
            im = NG.nhan(nd, co=52, nghieng=-3 if (i + k) % 2 else 2.5, hat=hat, font=font_cho("tay", nd))
        if im.width > W - 60:
            tl = (W - 60) / im.width
            im = im.resize((round(im.width * tl), round(im.height * tl)), Image.LANCZOS)
        p = D / "chu" / f"c{i + 1:02d}_{k}.png"
        p.parent.mkdir(parents=True, exist_ok=True)
        im.save(p)
        ra.append(p)
    return ra


def dat_chu(khung: Image.Image, cac: list[Image.Image]) -> list[tuple[int, int]]:
    """Chon cho dat chu IT CHI TIET nhat va KHONG de len vung giua khung.

    Chi dua vao nang luong canh la sai: anh tuyet trang o giua co rat it chi tiet nen bi
    tuong la cho trong — do duoc nhan de thang len doan nguoi leo nui. Nen phat theo PHAN
    DIEN TICH de len hop giua (50% ngang x 60% doc), noi chu the thuong nam. Cac nhan khong
    duoc chong len nhau. Xet 9 vi tri: 3 cot x 3 hang.
    """
    import numpy as np
    g = np.asarray(khung.convert("L").resize((W // 4, H // 4)), dtype=float)
    nang = np.abs(np.diff(g, axis=1, prepend=g[:, :1])) + np.abs(np.diff(g, axis=0, prepend=g[:1, :]))
    tp = np.pad(nang.cumsum(0).cumsum(1), ((1, 0), (1, 0)))    # anh tich phan -> TB vung bat ky O(1)

    def tb(x: int, y: int, w: int, h: int) -> float:
        a, b, c2, d = y // 4, x // 4, min(H // 4, (y + h) // 4), min(W // 4, (x + w) // 4)
        return (tp[c2, d] - tp[a, d] - tp[c2, b] + tp[a, b]) / max(1, (c2 - a) * (d - b))

    tb_ca = float(nang.mean()) + 1e-6                          # chuan hoa: 1 = chi tiet trung binh
    tx0, tx1, ty0, ty1 = W * 0.25, W * 0.75, H * 0.20, H * 0.80   # hop giua
    le, da_dat, ra = 28, [], []
    for im in cac:
        w, h = im.size
        tot = None
        for y in (le, (H - h) // 2, H - h - le):
            for x in (le, (W - w) // 2, W - w - le):
                if x < 0 or y < 0:
                    continue
                if any(x < ox + ow and ox < x + w and y < oy + oh and oy < y + h for ox, oy, ow, oh in da_dat):
                    continue
                de = (max(0, min(x + w, tx1) - max(x, tx0)) * max(0, min(y + h, ty1) - max(y, ty0))) / (w * h)
                diem = tb(x, y, w, h) / tb_ca + 4.0 * de
                if tot is None or diem < tot[0]:
                    tot = (diem, x, y)
        _, x, y = tot or (0, le, le)
        da_dat.append((x, y, w, h))
        ra.append((x, y))
    return ra


# ------------------------------------------------------------------------ dung

def dung(da: dict, D: Path, bao) -> Path:
    tm = D / ".tam_dung"
    shutil.rmtree(tm, ignore_errors=True)
    tm.mkdir()
    doan = []
    n = len(da["canh"])
    for i, c in enumerate(da["canh"]):
        nguon = D / "clip" / f"c{i + 1:02d}.mp4"
        d = float(c["giay"])
        cat = LV.tu_cat(nguon, d)
        kg = tm / f"g{i}.png"
        LV.chay([LV.FF, "-v", "error", "-y", "-ss", f"{d / 2:.3f}", "-i", str(nguon), "-frames:v", "1",
                 "-vf", f"{cat}scale={W}:{H}", str(kg)])
        pngs = ve_chu(i, c, D)
        vt = dat_chu(Image.open(kg), [Image.open(p) for p in pngs]) if pngs else []
        lenh = [LV.FF, "-v", "error", "-y", "-i", str(nguon)]
        for p in pngs:
            lenh += ["-i", str(p)]
        g = f"[0:v]trim=0:{d},setpts=PTS-STARTPTS,fps={FPS},{cat}scale={W}:{H},setsar=1[v0]"
        for k, (x, y) in enumerate(vt, 1):
            g += f";[v{k - 1}][{k}:v]overlay={x}:{y}[v{k}]"
        ra = tm / f"{i:02d}.mp4"
        lenh += ["-filter_complex", g, "-map", f"[v{len(vt)}]", "-t", str(d), "-c:v", "libx264",
                 "-crf", "14", "-preset", "medium", "-pix_fmt", "yuv420p", str(ra)]
        LV.chay(lenh)
        doan.append(ra)
        bao("dung", i + 1, n, f"canh {i + 1}" + (f" · cat {cat.rstrip(',')}" if cat else "")
            + (f" · chu tai {vt}" if vt else ""))
    ds = tm / "ds.txt"
    ds.write_text("".join(f"file '{p}'\n" for p in doan))
    ghep = tm / "ghep.mp4"
    LV.chay([LV.FF, "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(ds), "-c", "copy", str(ghep)])
    nhac = D / da["nhac"] if da.get("nhac") else None
    ra = D / "video.mp4"
    LV.hoan_thien(ghep, LV.do_dai(ghep), str(nhac) if nhac and nhac.exists() else None, str(ra))
    shutil.rmtree(tm, ignore_errors=True)
    return ra


def main() -> None:
    duong = Path(sys.argv[1]).resolve()
    D = duong.parent
    da = json.loads(duong.read_text(encoding="utf-8"))
    t0 = time.time()

    def luu(**kw) -> None:
        da.update(kw)
        duong.write_text(json.dumps(da, ensure_ascii=False, indent=2), encoding="utf-8")

    def bao(buoc: str, xong: int, tong: int, ghi: str = "") -> None:
        (D / "tien_do.json").write_text(json.dumps(
            {"buoc": buoc, "xong": xong, "tong": tong, "ghi": ghi, "giay": round(time.time() - t0)},
            ensure_ascii=False), encoding="utf-8")
        print(f"[{time.time() - t0:7.1f}s] {buoc} {xong}/{tong}  {ghi}", flush=True)

    n = len(da.get("canh") or [])
    if not n:
        sys.exit("Du an khong co canh nao.")
    luu(trang_thai="dang_chay", loi="")
    try:
        dam_bao_comfy()
        for i, c in enumerate(da["canh"]):
            bao("render", i, n, f"canh {i + 1}: {c['prompt'][:70]}")
            t = time.time()
            _, giu = render_canh(i, c, da, D)
            print(f"           -> c{i + 1:02d}.mp4 " + ("(giu ban cu, prompt khong doi)" if giu
                  else f"render xong sau {time.time() - t:.0f}s"), flush=True)
        bao("dung", 0, n, "ve chu, dat chu, ghep")
        ra = dung(da, D, bao)
        luu(trang_thai="xong", video=ra.name, giay_video=round(LV.do_dai(ra), 2),
            xong_luc=time.strftime("%Y-%m-%d %H:%M:%S"))
        bao("xong", n, n, ra.name)
        print(f"-> {ra}  {LV.do_dai(ra):.2f}s  {ra.stat().st_size / 1048576:.1f} MB  "
              f"(tong {time.time() - t0:.0f}s)", flush=True)
    except (Exception, SystemExit) as e:
        luu(trang_thai="loi", loi=str(e)[:800])
        bao("loi", 0, n, str(e)[:300])
        raise


if __name__ == "__main__":
    main()
