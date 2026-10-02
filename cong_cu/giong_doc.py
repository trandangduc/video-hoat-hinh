"""Doc loi kich ban thanh giong noi tieng Anh bang Chatterbox.

Chay tren GPU1 (dat CUDA_VISIBLE_DEVICES=1) de khong tranh VRAM voi LTX dang ve o GPU0.

  CUDA_VISIBLE_DEVICES=1 python cong_cu/giong_doc.py "Some narration." ra.wav [--giong-mau mau.wav] [--cam-xuc vui]

Loi dai duoc tach theo cau roi noi lai voi mot quang nghi ngan: Chatterbox doc mot hoi
qua dai de bi lap tu hoac nuot chu. Khoang lang dau/cuoi bi cat bot, vi DO DAI GIONG quyet
dinh do dai canh — im lang thua lam canh dai vo ich.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import chung as C  # noqa: E402

TOI_DA_KY_TU = 220      # mot hoi doc
NGHI = 0.28             # giay nghi giua cac cau
LE = 0.12               # giu lai bay nhieu giay truoc tieng dau / sau tieng cuoi
_MODEL = None


def nap(thiet_bi: str):
    global _MODEL
    if _MODEL is None:
        from chatterbox.tts import ChatterboxTTS
        _MODEL = ChatterboxTTS.from_pretrained(device=thiet_bi)
    return _MODEL


def tach_cau(chu: str) -> list[str]:
    cau = [c.strip() for c in re.split(r"(?<=[.!?;])\s+", chu.strip()) if c.strip()]
    ra, hang = [], ""
    for c in cau:
        if hang and len(hang) + 1 + len(c) > TOI_DA_KY_TU:
            ra.append(hang)
            hang = c
        else:
            hang = f"{hang} {c}".strip()
    if hang:
        ra.append(hang)
    return ra


def cat_lang(x, sr: int):
    import numpy as np
    a = np.abs(x)
    nguong = max(1e-4, a.max() * 0.02)
    co = np.where(a > nguong)[0]
    if not len(co):
        return x
    le = int(LE * sr)
    return x[max(0, co[0] - le): min(len(x), co[-1] + le)]


def doc(chu: str, ra: Path, giong_mau: Path | None = None, cam_xuc: str = "binh_thuong") -> dict:
    import numpy as np
    import soundfile as sf
    import torch
    thiet_bi = "cuda" if torch.cuda.is_available() else "cpu"
    m = nap(thiet_bi)
    ex, cfg = C.CAM_XUC.get(cam_xuc, C.CAM_XUC["binh_thuong"])
    kw = {"exaggeration": ex, "cfg_weight": cfg}
    if giong_mau:
        kw["audio_prompt_path"] = str(giong_mau)
    t0 = time.time()
    doan = []
    for i, cau in enumerate(tach_cau(chu)):
        w = m.generate(cau, **kw).detach().cpu().squeeze(0).numpy()
        w = cat_lang(w, m.sr)
        if i:
            doan.append(np.zeros(int(NGHI * m.sr), dtype=w.dtype))
        doan.append(w)
    ra.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(ra), np.concatenate(doan), m.sr)
    return {"giay": round(C.do_dai_wav(ra), 2), "sinh_mat": round(time.time() - t0, 1), "so_hoi": len(doan) // 2 + 1}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("chu")
    ap.add_argument("ra")
    ap.add_argument("--giong-mau")
    ap.add_argument("--cam-xuc", default="binh_thuong", choices=list(C.CAM_XUC))
    a = ap.parse_args()
    import torch
    t0 = time.time()
    kq = doc(a.chu, Path(a.ra), Path(a.giong_mau) if a.giong_mau else None, a.cam_xuc)
    kq["tong_ca_nap"] = round(time.time() - t0, 1)
    if torch.cuda.is_available():
        kq["vram_dinh_gb"] = round(torch.cuda.max_memory_allocated() / 1073741824, 2)
    print(json.dumps(kq, ensure_ascii=False))


if __name__ == "__main__":
    main()
