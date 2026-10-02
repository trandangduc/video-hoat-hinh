"""Sinh ANH TINH bang chinh LTX-2.5 (text-to-image), khong can model anh rieng.

LTX chap nhan length = 1 khung (8n+1 voi n=0), nen dua workflow t2v dev vao
voi 1 khung la ra mot buc anh. Dung de lam buoc IMAGE trong quy trinh
anh -> i2v: sinh anh mau dung ti le khung video (khong phai dem 1:1 thanh
16:9 roi lam mo hai ben nhu anh Gemini).

  python cong_cu/tao_anh_ltx.py --ten collage_01 --prompt "..." [--seed 7]
  -> vao/canh/collage_01.png
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.request
import uuid
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import chung as C

MAY = "http://127.0.0.1:8188"
AM = "blurry, distorted, watermark, low quality"


def goi(duong: str, du_lieu: dict | None = None) -> dict:
    req = urllib.request.Request(
        MAY + duong,
        data=json.dumps(du_lieu).encode() if du_lieu is not None else None,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--ten", required=True)
    p.add_argument("--prompt", required=True)
    p.add_argument("--rong", type=int, default=1280)
    p.add_argument("--cao", type=int, default=704)
    p.add_argument("--seed", type=int, default=1234)
    a = p.parse_args()

    wf = json.loads((C.WORKFLOWS / "ltx25_t2v_dev.json").read_text(encoding="utf-8"))
    wf["30"]["inputs"]["text"] = a.prompt
    wf["31"]["inputs"]["text"] = AM
    wf["40"]["inputs"].update(width=a.rong, height=a.cao, length=1)
    wf["42"]["inputs"]["frames_number"] = 1
    wf["51"]["inputs"]["noise_seed"] = a.seed
    tien_to = f"anh_ltx/{a.ten}_{uuid.uuid4().hex[:6]}"
    wf["70"]["inputs"]["filename_prefix"] = tien_to
    wf["71"]["inputs"]["filename_prefix"] = tien_to + "_am"

    t0 = time.time()
    pid = goi("/prompt", {"prompt": wf, "client_id": "anh-" + uuid.uuid4().hex[:8]})["prompt_id"]
    while True:
        time.sleep(2)
        h = goi(f"/history/{pid}").get(pid)
        if not h:
            continue
        tt = h.get("status", {})
        if tt.get("status_str") == "error":
            raise SystemExit(f"ComfyUI bao loi: {json.dumps(tt)[:800]}")
        if tt.get("completed"):
            break

    anh = [im for n in h["outputs"].values() for im in n.get("images", [])]
    if not anh:
        raise SystemExit("Khong ra anh nao.")
    im = anh[0]
    nguon = C.COMFY / "output" / (im.get("subfolder") or "") / im["filename"]
    dich = C.CANH / f"{a.ten}.png"
    C.CANH.mkdir(parents=True, exist_ok=True)
    shutil.copy(nguon, dich)
    print(f"-> {dich.relative_to(GOC)}  {a.rong}x{a.cao}  sau {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
