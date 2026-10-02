"""Thu IC-LoRA Ingredients cho LTX-2.5 — do dong nhat nhan vat qua nhieu canh.

  python cong_cu/thu_ingredients.py dev_lora_1 distilled_lora_1 distilled_khong_2 ...
  ten = <model>_<lora|khong>_<so canh>  -> ra/thu_ingredients/<ten>.mp4 + logs/thu_ingredients.jsonl

Theo model card (README cua repo):
  - huan luyen tren LTX-2.5 DEV, 768x448, 121 khung, 24 fps -> ve dung kich thuoc do
  - bang tham chieu la VIDEO TINH (anh lap du so khung), cung do phan giai video (downscale 1)
  - prompt 2 phan "Reference sheet: <ta TUNG O cua bang> Generated video: <canh>"
  - prompt am goi y: worst quality, inconsistent motion, blurry, jittery, distorted
Workflow ComfyUI chinh thuc thi chay tren DISTILLED (8 buoc, cfg 1, euler_ancestral_cfg_pp) -> thu ca hai.

Lan thu 1 (960x544, bang 2 hinh tren nen den, prompt ta chung): video CHEP NGUYEN bo cuc bang. Bang moi dung
theo video mau: o nen xam phu kin khung (cong_cu/tach_nen.py).

ComfyUI nay KHONG co LTXICLoRALoaderModelOnly / LTXAddVideoICLoRAGuide -> node goc tuong duong:
LoraLoaderModelOnly + GetICLoRAParameters + LTXVAddGuide(iclora_parameters) + LTXVCropGuides.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import du_an as DA  # noqa: E402

RA = GOC / "ra" / "thu_ingredients"
LOG = GOC / "logs" / "thu_ingredients.jsonl"
LORA = "ltx-2.5-22b-ic-lora-ingredients-0.9.safetensors"
BANG = GOC / "vao" / "tham_chieu" / os.environ.get("BANG", "non_la_bang.png")   # BANG=non_la_bang1.png de thu bang khac
W, H, K, HAT = 768, 448, 121, 42
AM = "worst quality, inconsistent motion, blurry, jittery, distorted, text, letters"
TA_BANG = (
    "**Left (Character):** A front-facing close-up of a flat 2D cartoon man drawn with thick black outlines: a big "
    "round beige head, small black dot eyes, angry slanted eyebrows and a stern flat mouth, wearing a woven conical "
    "straw hat. **Right (Character):** "
    + ("A full-body front view of the same man: " if "bang1" in BANG.name else
       "A full-body turnaround of the same man, front view and mirrored front view: ")
    + "a small slim body, an open short-sleeved pink shirt with large cream hibiscus flowers over a beige undershirt, "
    "matching pink floral shorts with a white drawstring, bare beige legs and feet, one arm pointing to the side.")
NHAN_VAT = ("the flat 2D cartoon man with a big round head, a woven conical straw hat, an open pink hibiscus shirt "
            "and pink floral shorts")
CANH = [
    "walks through deep snow in a mountain pass at dawn, leaving footprints, cold mist in the air; slow tracking shot",
    "sits at an old wooden desk writing in a notebook under a warm desk lamp, frowning in concentration; slow push-in",
    "stands in a dusty archive room and points at a large hand-drawn map pinned on the wall; slow pan",
]
PHONG_CACH = "A flat 2D cartoon animation with thick black outlines and flat saturated colours."


def wf_nen(prompt: str, ten: str, model: str) -> dict:
    wf = DA.wf_ve(prompt, K, HAT, None, ten)          # dev: LTXVDualCFGGuider 3/7, 30 buoc
    wf["40"]["inputs"].update(width=W, height=H)
    wf["31"]["inputs"]["text"] = AM
    if model.startswith("distilled"):                 # nhu workflow chinh thuc
        wf["10"]["inputs"]["unet_name"] = DA.UNET_NHANH
        wf["50"] = {"class_type": "CFGGuider", "inputs": {"model": ["10", 0], "positive": ["32", 0],
                                                          "negative": ["32", 1], "cfg": 1.0}}
        wf["52"]["inputs"]["sampler_name"] = "euler_ancestral_cfg_pp"
        wf["53"] = {"class_type": "ManualSigmas", "inputs": {"sigmas": DA.SIGMAS_DISTILLED}}
    return wf


def wf_lora(i: int, ten: str, model: str) -> dict:
    prompt = f"Reference sheet: {TA_BANG} Generated video: {PHONG_CACH} {NHAN_VAT[0].upper() + NHAN_VAT[1:]} {CANH[i]}"
    wf = wf_nen(prompt, ten, model)
    wf["110"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["10", 0], "lora_name": LORA, "strength_model": 1.0}}
    wf["111"] = {"class_type": "GetICLoRAParameters", "inputs": {"iclora_model": ["110", 0]}}
    wf["112"] = {"class_type": "LoadImage", "inputs": {"image": BANG.name}}
    wf["113"] = {"class_type": "RepeatImageBatch", "inputs": {"image": ["112", 0], "amount": K}}   # bang -> video tinh
    wf["114"] = {"class_type": "LTXVAddGuide", "inputs": {"positive": ["32", 0], "negative": ["32", 1], "vae": ["12", 0],
                                                         "latent": ["40", 0], "image": ["113", 0], "frame_idx": 0,
                                                         "strength": 1.0, "iclora_parameters": ["111", 0]}}
    wf["43"]["inputs"]["video_latent"] = ["114", 2]
    wf["50"]["inputs"].update(model=["110", 0], positive=["114", 0], negative=["114", 1])
    wf["115"] = {"class_type": "LTXVCropGuides", "inputs": {"positive": ["114", 0], "negative": ["114", 1], "latent": ["60", 0]}}
    wf["61"]["inputs"]["samples"] = ["115", 2]                                                    # chi giai ma video that
    return wf


def hai_tang(wf: dict, co_guide: bool, sigmas2: str | None = None, dich: tuple[int, int] = (1280, 704)) -> dict:
    """Nhu che do Nhanh cua Xuong (model 'distilled2t'): tang 1 640x352 -> phong latent x2 -> tang 2 3 buoc o 1280x704.
    Co LoRA: tang 1 ve kem bang tham chieu; tang 2 tinh chinh bang model distilled TRON tren latent da cat guide, va
    conditioning cung la ban da cat (115) vi keyframe_idxs cua guide khong con khop latent tang 2."""
    wf["40"]["inputs"].update(width=dich[0], height=dich[1])
    DA.them_tang_2(wf, HAT, False)                    # 40 -> nua dich (1280x704 -> 640x352), them 100..107, 61 doc 106
    if sigmas2:
        wf["103"]["inputs"]["sigmas"] = sigmas2
    if co_guide:
        wf["101"]["inputs"]["samples"] = ["115", 2]
        wf["116"] = {"class_type": "CFGGuider", "inputs": {"model": ["10", 0], "positive": ["115", 0],
                                                           "negative": ["115", 1], "cfg": 1.0}}
        wf["105"]["inputs"]["guider"] = ["116", 0]
    return wf


def wf_khong(i: int, ten: str, model: str) -> dict:
    """Cach tot nhat Xuong co khi khong co LoRA: ta nhan vat bang chu vao prompt."""
    return wf_nen(f"{PHONG_CACH} {NHAN_VAT[0].upper() + NHAN_VAT[1:]} {CANH[i]}", ten, model)


def main() -> None:
    ds = sys.argv[1:] or ["dev_lora_1", "distilled_lora_1"]
    if not (GOC / "models" / "loras" / LORA).exists():
        sys.exit(f"Chua co models/loras/{LORA}")
    if not BANG.exists():
        sys.exit(f"Chua co {BANG} — chay cong_cu/tach_nen.py truoc")
    RA.mkdir(parents=True, exist_ok=True)
    shutil.copy(BANG, DA.COMFY / "input" / BANG.name)
    for ten in ds:
        model, kieu, so = ten.rsplit("_", 2)
        i = int(so) - 1
        wf = (wf_lora if kieu == "lora" else wf_khong)(i, f"thu_ingredients/{ten}", model)
        kt = f"{W}x{H}"
        if model == "distilled2t":
            hai_tang(wf, kieu == "lora")
            kt = "1280x704 (2 tang)"
        elif model == "distilled2tlo":
            # distilled2t_lora_1: tang 2 tu sigma 0.85 KHONG co LoRA ve lai chi tiet theo kieu anh that -> mat mat,
            # mat hoa van quan. Bat dau tang 2 thap hon de chi lam net.
            hai_tang(wf, kieu == "lora", "0.4219, 0.2, 0.0")
            kt = "1280x704 (2 tang, tang 2 tu sigma 0.42)"
        elif model == "distilled768x2":
            # distilled2t_lora_2: tang 1 o 640x352 (lech bucket 768x448, bang bi cat giua) -> CHEP NGUYEN bang.
            # Tang 1 phai dung 768x448; phong x2 len 1536x896, tang 2 chi lam net (sigma thap), merge thu ve 1280x720.
            hai_tang(wf, kieu == "lora", "0.4219, 0.2, 0.0", dich=(2 * W, 2 * H))
            kt = f"{2 * W}x{2 * H} (tang 1 {W}x{H}, tang 2 tu sigma 0.42)"
        t0 = time.time()
        try:
            giay, loi = DA.chay_wf(wf, RA / f"{ten}.mp4", ten), ""
        except Exception as e:
            giay, loi = None, str(e)[:500]
        kq = {"ten": ten, "giay_ve": round(giay, 1) if giay else None, "tong": round(time.time() - t0),
              "loi": loi, "bang": BANG.name, "kich_thuoc": kt, "luc": time.strftime("%H:%M:%S")}
        print(json.dumps(kq, ensure_ascii=False), flush=True)
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(kq, ensure_ascii=False) + "\n")
    print("XONG THU INGREDIENTS", flush=True)


if __name__ == "__main__":
    main()
