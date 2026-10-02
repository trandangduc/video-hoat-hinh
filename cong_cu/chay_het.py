"""Chay ca 3 buoc theo dung thu tu TTS -> video -> ghep.

Thu tu nay la BAT BUOC: Wan 2.2 S2V nhan audio lam dau vao, do dai audio quyet
dinh do dai clip. Lam video truoc roi moi TTS la phai cat/keo cho khop.

  python cong_cu/chay_het.py
  python cong_cu/chay_het.py --lam-lai
  python cong_cu/chay_het.py --kich-ban vao/kich_ban_t2v_full.json --ra ra/video_t2v.mp4
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "scripts"))
import chung as C

PY_VENV = str(GOC / ".venv" / "bin" / "python")

BUOC = [
    ("1/3  TTS      (kich ban -> ra/tieng/*.wav)", "scripts/01_tts.py", "logs/do_tts.json"),
    ("2/3  Hoat hinh (anh + wav -> ra/clip/*.mp4)", "scripts/02_hoat_hinh.py", "logs/do_video.json"),
    ("3/3  Ghep     (clip + phu de -> video_cuoi.mp4)", "scripts/03_ghep.py", "logs/do_ghep.json"),
]


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--lam-lai", action="store_true")
    p.add_argument("--kich-ban", help="dung file kich ban khac vao/kich_ban.json")
    p.add_argument("--ra", help="duong dan video cuoi, mac dinh ra/video_cuoi.mp4")
    a = p.parse_args()

    t0 = time.time()
    for i, (ten, script, do) in enumerate(BUOC, 1):
        print(f"\n{'=' * 64}\n  {ten}\n{'=' * 64}", flush=True)
        lenh = [PY_VENV, script, "--do", do]
        # Ca ba script deu nhan --kich-ban; rieng --ra chi buoc ghep hieu.
        if a.kich_ban:
            lenh += ["--kich-ban", a.kich_ban]
        if a.ra and i == 3:
            lenh += ["--ra", a.ra]
        if a.lam_lai and i < 3:
            lenh.append("--lam-lai")
        r = subprocess.run(lenh, cwd=str(GOC))
        if r.returncode:
            print(f"\nDUNG LAI o buoc {i}: script bao loi (ma {r.returncode}).",
                  file=sys.stderr)
            raise SystemExit(r.returncode)

    print(f"\n{'=' * 64}")
    print(f"  HOAN TAT sau {(time.time() - t0) / 60:.1f} phut")
    print(f"  -> {a.ra or C.VIDEO_CUOI}")
    print(f"{'=' * 64}")


if __name__ == "__main__":
    main()
