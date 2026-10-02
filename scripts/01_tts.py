"""Buoc 1/3 -- kich_ban.json  ->  ra/tieng/<id>.wav

CHAY TRUOC BUOC 2, khong duoc dao. Wan 2.2 S2V nhan audio lam dau vao va
sinh clip khop mieng theo do dai audio do; lam video truoc thi phai cat/keo
cho khop, hong ca nhip.

  python scripts/01_tts.py                # tat ca canh co thoai
  python scripts/01_tts.py --canh canh_01 # dung mot canh
  python scripts/01_tts.py --lam-lai      # ghi de wav da co
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import chung as C


def nap_model(thiet_bi: str):
    from chatterbox.tts import ChatterboxTTS

    C.buoc(f"Nap Chatterbox len {thiet_bi} (lan dau phai tai ~1 GB tu HuggingFace)")
    t = time.time()
    m = ChatterboxTTS.from_pretrained(device=thiet_bi)
    C.noi(f"nap xong sau {time.time() - t:.1f}s, sample rate {m.sr} Hz")
    return m


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--canh", help="chi lam dung mot canh, vi du canh_01")
    p.add_argument("--kich-ban", help="duong dan file kich ban JSON, mac dinh vao/kich_ban.json")
    p.add_argument("--lam-lai", action="store_true", help="ghi de wav da co")
    p.add_argument("--thiet-bi", default="cuda")
    p.add_argument("--do", help="ghi so do ra file json")
    a = p.parse_args()

    kb = C.doc_kich_ban(Path(a.kich_ban) if getattr(a, "kich_ban", None) else None)
    van_de = [v for v in C.kiem_kich_ban(kb) if "khong thay anh" not in v]
    if van_de:
        C.loi("Kich ban co van de:\n  - " + "\n  - ".join(van_de))

    canh = [c for c in kb.canh if c.co_thoai]
    if a.canh:
        canh = [c for c in canh if c.id == a.canh]
        if not canh:
            C.loi(f"Khong co canh co thoai nao ten '{a.canh}'.")

    C.TIENG.mkdir(parents=True, exist_ok=True)
    can_lam = [c for c in canh if a.lam_lai or not c.duong_wav.exists()]
    C.buoc(f"{len(canh)} canh co thoai, can sinh {len(can_lam)}")
    if not can_lam:
        C.noi("Khong co gi de lam.")
        return

    giong_mau = C.GIONG_MAU if C.GIONG_MAU.exists() else None
    C.noi(f"giong mau: {giong_mau.name if giong_mau else 'khong co -> dung giong mac dinh'}")

    import soundfile as sf
    import torch

    thiet_bi = a.thiet_bi if torch.cuda.is_available() else "cpu"
    if thiet_bi.startswith("cuda"):
        torch.cuda.reset_peak_memory_stats()
    model = nap_model(thiet_bi)

    do = {"buoc": "tts", "thiet_bi": thiet_bi, "canh": []}
    tong = time.time()
    for i, c in enumerate(can_lam, 1):
        ex, cfg = c.tham_so_giong()
        C.buoc(f"[{i}/{len(can_lam)}] {c.id}  cam_xuc={c.cam_xuc} "
               f"(exaggeration={ex}, cfg_weight={cfg})")
        C.noi(f'"{c.thoai[:70]}{"..." if len(c.thoai) > 70 else ""}"')
        t = time.time()
        kw = {"exaggeration": ex, "cfg_weight": cfg}
        if giong_mau:
            kw["audio_prompt_path"] = str(giong_mau)
        wav = model.generate(c.thoai, **kw)
        # torchaudio.save cua ban 2.11 doi torchcodec; soundfile ghi WAV truc tiep,
        # it phu thuoc hon. wav ra tu Chatterbox la (1, N) -> bo chieu kenh.
        sf.write(str(c.duong_wav), wav.detach().cpu().squeeze(0).numpy(), model.sr)
        giay_lam = time.time() - t
        giay_tieng = C.do_dai_wav(c.duong_wav)
        C.noi(f"-> {c.duong_wav.name}  dai {giay_tieng:.2f}s  "
              f"(sinh mat {giay_lam:.1f}s = {giay_lam / max(giay_tieng, .01):.1f}x thoi luong)")
        do["canh"].append({"id": c.id, "giay_sinh": round(giay_lam, 2),
                           "giay_tieng": round(giay_tieng, 2),
                           "cam_xuc": c.cam_xuc, "exaggeration": ex, "cfg_weight": cfg})

    if thiet_bi.startswith("cuda"):
        do["vram_dinh_gb"] = round(torch.cuda.max_memory_allocated() / 1073741824, 2)
        C.noi(f"VRAM dinh cua buoc TTS: {do['vram_dinh_gb']} GB")
    do["giay_tong"] = round(time.time() - tong, 2)
    C.buoc(f"XONG buoc TTS sau {do['giay_tong']}s")

    if a.do:
        Path(a.do).write_text(json.dumps(do, ensure_ascii=False, indent=2), encoding="utf-8")
        C.noi(f"so do ghi vao {a.do}")


if __name__ == "__main__":
    main()
