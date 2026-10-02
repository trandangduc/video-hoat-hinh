"""Do toc do ve LTX-2.5 theo nhieu cau hinh tren CUNG mot canh (cung prompt, cung seed).

  python cong_cu/do_toc_do.py goc buoc20 easycache lazycache
  -> ra/do_toc_do/<ten>.mp4  (de so chat luong)  +  mot dong JSON moi cau hinh vao logs/do_toc_do.jsonl

Luot "am" (9 khung, 2 buoc) chay dau tien de nap model — khong tinh vao so do.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import du_an as DA  # noqa: E402

RA = GOC / "ra" / "do_toc_do"
LOG = GOC / "logs" / "do_toc_do.jsonl"
PROMPT = ("vintage sepia and black-and-white collage, torn paper edges, handwritten notes, old scientific "
          "illustrations: an old photograph pinned among torn notebook pages showing six hikers in heavy winter "
          "jackets and large backpacks walking through deep snow toward the camera, slow push-in")
K, HAT = 121, 4242          # 121 khung = 5.04 giay


def wf_goc(k: int = K, buoc: int = 30) -> dict:
    wf = DA.wf_ve(PROMPT, k, HAT, None, "do_toc_do/tam")
    wf["53"]["inputs"]["steps"] = buoc
    return wf


def boc_cache(wf: dict, loai: str, nguong: float) -> dict:
    wf["90"] = {"class_type": loai, "inputs": {"model": ["10", 0], "reuse_threshold": nguong,
                                               "start_percent": 0.15, "end_percent": 0.95, "verbose": True}}
    wf["50"]["inputs"]["model"] = ["90", 0]
    return wf


def distilled(k: int = K) -> dict:
    """Model distilled nvfp4 dung nhu workflow chinh thuc LTX-2.5_T2V_I2V_Two_Stage_Distilled:
    8 buoc sigma dat tay, CFGGuider cfg 1 -> ComfyUI bo luot am, moi buoc chay model 1 lan (dev: 2 lan x 30 buoc)."""
    wf = wf_goc(k)
    wf["10"]["inputs"]["unet_name"] = "ltx-2.5-22b-distilled-transformer-nvfp4.safetensors"
    wf["50"] = {"class_type": "CFGGuider", "inputs": {"model": ["10", 0], "positive": ["32", 0],
                                                      "negative": ["32", 1], "cfg": 1.0}}
    wf["53"] = {"class_type": "ManualSigmas",
                "inputs": {"sigmas": "1.0, 0.99375, 0.9875, 0.98125, 0.975, 0.909375, 0.725, 0.421875, 0.0"}}
    return wf


def hai_tang(buoc1: int = 30, sigmas2: str = "0.85, 0.7250, 0.4219, 0.0", cache: str | None = None,
             nen: dict | None = None, sampler2: str | None = None) -> dict:
    """Ve 2 tang nhu pipeline chinh thuc cua LTX-2 (ti2vid_two_stages.py): tang 1 ve NUA do phan giai
    (640x352), phong x2 trong latent, tang 2 tinh chinh 3 buoc tu sigma 0.85 bang CUNG guider/sampler.
    nen=None: model dev + CFG (ban chinh thuc tinh chinh tang 2 bang distilled LoRA — khong tai them);
    nen=distilled(): ca hai tang bang model distilled, dung nhu workflow chinh thuc."""
    wf = nen if nen is not None else wf_goc(buoc=buoc1)
    wf["40"]["inputs"].update(width=640, height=352)
    wf["100"] = {"class_type": "LatentUpscaleModelLoader",
                 "inputs": {"model_name": "ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"}}
    wf["101"] = {"class_type": "LTXVLatentUpsampler", "inputs": {"samples": ["60", 0], "upscale_model": ["100", 0], "vae": ["12", 0]}}
    wf["102"] = {"class_type": "LTXVConcatAVLatent", "inputs": {"video_latent": ["101", 0], "audio_latent": ["60", 1]}}
    wf["103"] = {"class_type": "ManualSigmas", "inputs": {"sigmas": sigmas2}}
    wf["104"] = {"class_type": "RandomNoise", "inputs": {"noise_seed": HAT + 1}}
    wf["105"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["104", 0], "guider": ["50", 0], "sampler": ["52", 0],
                                                                   "sigmas": ["103", 0], "latent_image": ["102", 0]}}
    wf["106"] = {"class_type": "LTXVSeparateAVLatent", "inputs": {"av_latent": ["105", 0]}}
    wf["61"]["inputs"]["samples"] = ["106", 0]
    if sampler2:            # euler_ancestral them nhieu moi buoc -> 3 buoc dev khong khu het van luoi cua bo phong
        wf["107"] = {"class_type": "KSamplerSelect", "inputs": {"sampler_name": sampler2}}
        wf["105"]["inputs"]["sampler"] = ["107", 0]
    if cache:
        boc_cache(wf, cache, 0.2)
    return wf


CAU_HINH = {
    "hai_tang": lambda: hai_tang(),
    "hai_tang_20": lambda: hai_tang(20),
    "hai_tang_cache": lambda: hai_tang(cache="EasyCache"),
    # hai_tang (3 buoc euler_ancestral o tang 2) con van luoi lam tam o 100% -> 2 cach sua
    "hai_tang_euler": lambda: hai_tang(sampler2="euler"),
    "hai_tang_s2_8": lambda: hai_tang(sampler2="euler",
                                      sigmas2="0.85, 0.78, 0.70, 0.60, 0.48, 0.35, 0.22, 0.10, 0.0"),
    "am": lambda: wf_goc(9, 2),
    "goc": lambda: wf_goc(),
    "buoc20": lambda: wf_goc(buoc=20),
    "easycache": lambda: boc_cache(wf_goc(), "EasyCache", 0.2),
    "lazycache": lambda: boc_cache(wf_goc(), "LazyCache", 0.2),
    # nguong 0.2 khong bo duoc buoc nao (muc thay doi cua LTX ~0.53) -> thu 0.5
    "easycache_05": lambda: boc_cache(wf_goc(), "EasyCache", 0.5),
    "distilled": lambda: distilled(),
    "distilled_2tang": lambda: hai_tang(nen=distilled()),
}


def luot_am(wf: dict) -> dict:
    """Ban thu nho (9 khung, 2 buoc) cua CHINH cau hinh dau tien: nap dung model se do.
    Nap nham model khac (vd dev truoc distilled) thi ComfyUI giu ca hai trong RAM -> tran 60 GB."""
    wf["40"]["inputs"]["length"] = 9
    wf["42"]["inputs"]["frames_number"] = 9
    s = wf["53"]["inputs"]
    if "steps" in s:
        s["steps"] = 2
    else:
        s["sigmas"] = "1.0, 0.5, 0.0"
    return wf


def vram() -> int:
    r = subprocess.run(["nvidia-smi", "--id=0", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                       capture_output=True, text=True)
    return int(r.stdout.strip() or 0)


def chay(ten: str, wf: dict) -> dict:
    wf["70"]["inputs"]["filename_prefix"] = f"do_toc_do/{ten}"
    wf["71"]["inputs"]["filename_prefix"] = f"do_toc_do/{ten}_am"
    dinh, chay_tiep = [vram()], [True]

    def theo():
        while chay_tiep[0]:
            dinh.append(vram())
            time.sleep(0.5)
    th = threading.Thread(target=theo, daemon=True)
    th.start()
    log = GOC / "logs" / "comfy.log"
    moc = log.stat().st_size
    try:
        giay = DA.chay_wf(wf, RA / f"{ten}.mp4", ten)
        loi = ""
    except Exception as e:
        giay, loi = None, str(e)[:400]
    chay_tiep[0] = False
    th.join()
    with open(log, "rb") as f:
        f.seek(moc)
        moi = f.read().decode("utf-8", "replace")
    cache = [l.strip() for l in moi.splitlines() if "cache" in l.lower() and ("skip" in l.lower() or "reuse" in l.lower() or "step" in l.lower())]
    return {"ten": ten, "giay_ve": round(giay, 1) if giay else None, "vram_dinh_mib": max(dinh),
            "cache_log": cache[-2:], "loi": loi, "luc": time.strftime("%H:%M:%S")}


def main() -> None:
    RA.mkdir(parents=True, exist_ok=True)
    ds = [x for x in sys.argv[1:] if x in CAU_HINH and x != "am"]
    for x in sys.argv[1:]:
        if x not in CAU_HINH:
            print(json.dumps({"ten": x, "loi": "khong co cau hinh nay"}), flush=True)
    for ten in (["am"] if ds else []) + ds:
        kq = chay(ten, luot_am(CAU_HINH[ds[0]]()) if ten == "am" else CAU_HINH[ten]())
        print(json.dumps(kq, ensure_ascii=False), flush=True)
        if ten != "am":
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(json.dumps(kq, ensure_ascii=False) + "\n")
    print("XONG DO TOC DO", flush=True)


if __name__ == "__main__":
    main()
