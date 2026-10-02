"""Tach nhan vat khoi nen (BiRefNet trong ComfyUI) roi dung BANG THAM CHIEU cho IC-LoRA Ingredients.

Bang theo dung video mau cua model (examples/ingredients_lora_*.mp4): phu gan kin khung, moi yeu to mot O
NEN XAM NHAT, mau den chi la khe va vien, khong chu; nhan vat = o can mat + o toan than nhieu goc.
Ban dau (2 hinh tren nen den trong) khien model chep nguyen bo cuc bang vao video.

Chi co mot anh nhin tu truoc -> "nhieu goc" = dang truoc + dang lat guong.

  python cong_cu/tach_nen.py vao/canh/canh_01.png vao/tham_chieu/non_la_bang.png [768 448]
"""
from __future__ import annotations

import json
import shutil
import sys
import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import du_an as DA  # noqa: E402

XAM = (214, 214, 214)
KHE = 8


def mat_na(anh: Path) -> Image.Image:
    """Mat na nhan vat (L, 0-255) cung kich thuoc anh goc, tinh bang BiRefNet qua ComfyUI."""
    ten = f"tach_{uuid.uuid4().hex[:6]}{anh.suffix}"
    shutil.copy(anh, DA.COMFY / "input" / ten)
    wf = {"1": {"class_type": "LoadImage", "inputs": {"image": ten}},
          "2": {"class_type": "LoadBackgroundRemovalModel", "inputs": {"bg_removal_name": "birefnet.safetensors"}},
          "3": {"class_type": "RemoveBackground", "inputs": {"bg_removal_model": ["2", 0], "image": ["1", 0]}},
          "4": {"class_type": "MaskToImage", "inputs": {"mask": ["3", 0]}},
          "5": {"class_type": "SaveImage", "inputs": {"images": ["4", 0], "filename_prefix": f"tach_nen/{ten}"}}}
    try:
        # chay_wf dong goi khung thanh mp4 (mat do chinh xac cua mat na) nen goi thang API o day
        pid = DA.goi("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex})["prompt_id"]
        while True:
            time.sleep(1.5)
            h = DA.goi(f"/history/{pid}").get(pid)
            if h and h.get("status", {}).get("status_str") == "error":
                raise RuntimeError(json.dumps(h["status"].get("messages", []), ensure_ascii=False)[:500])
            if h and h.get("status", {}).get("completed"):
                break
        im = [x for n in h["outputs"].values() for x in n.get("images", [])][0]
        p = DA.COMFY / "output" / (im.get("subfolder") or "") / im["filename"]
        m = Image.open(p).convert("L")
        p.unlink(missing_ok=True)
        return m
    finally:
        (DA.COMFY / "input" / ten).unlink(missing_ok=True)


def dat_vao(bang: Image.Image, nguon: Image.Image, hop: tuple[int, int, int, int], le: int = 10,
            day: str = "giua") -> None:
    """Dat anh RGBA vao hop, giu ti le; day='duoi' thi cham chan xuong day o (dang dung)."""
    x0, y0, x1, y1 = hop
    tl = min((x1 - x0 - 2 * le) / nguon.width, (y1 - y0 - 2 * le) / nguon.height)
    n = nguon.resize((max(1, int(nguon.width * tl)), max(1, int(nguon.height * tl))), Image.LANCZOS)
    y = y1 - le - n.height if day == "duoi" else y0 + (y1 - y0 - n.height) // 2
    bang.paste(n, (x0 + (x1 - x0 - n.width) // 2, y), n.split()[-1])


def o_xam(bang: Image.Image, hop: tuple[int, int, int, int]) -> None:
    bang.paste(Image.new("RGBA", (hop[2] - hop[0], hop[3] - hop[1]), XAM + (255,)), hop[:2])


def dung_bang(goc: Image.Image, m: Image.Image, W: int, H: int, guong: bool = True) -> Image.Image:
    """guong=False: chi mot dang toan than (lon hon). Thu 11/09: dang lat guong y het bi model hieu thanh
    NGUOI THU HAI (distilled2t_lora_3 ve hai nhan vat dung canh nhau)."""
    a = np.asarray(m)
    ys, xs = np.where(a > 128)
    if not len(xs):
        raise SystemExit("BiRefNet khong tim thay chu the nao.")
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    rgba = goc.copy()
    rgba.putalpha(m)
    than = rgba.crop((x0, y0, x1 + 1, y1 + 1))
    cao = y1 - y0
    tren = a[y0:y0 + int(cao * 0.33)] > 128                   # be ngang cua non + dau, khong tinh tay chia ra
    cot = np.where(tren.any(axis=0))[0]
    mat = rgba.crop((cot.min(), y0, cot.max() + 1, y0 + int(cao * 0.38)))

    bang = Image.new("RGBA", (W, H), (0, 0, 0, 255))
    rong_mat = int(W * 0.36)
    o_mat = (KHE, KHE, KHE + rong_mat, H - KHE)
    o_than = (2 * KHE + rong_mat, KHE, W - KHE, H - KHE)
    o_xam(bang, o_mat)
    o_xam(bang, o_than)
    dat_vao(bang, mat, o_mat)
    if guong:
        giua = (o_than[0] + o_than[2]) // 2
        dat_vao(bang, than, (o_than[0], o_than[1], giua, o_than[3]), day="duoi")
        dat_vao(bang, ImageOps.mirror(than), (giua, o_than[1], o_than[2], o_than[3]), day="duoi")
    else:
        dat_vao(bang, than, o_than, day="duoi")
    return bang.convert("RGB")


def dung_bang_tu_anh(anh: Path, ra: Path, W: int = 768, H: int = 448, guong: bool = True) -> Path:
    """Cho Xuong: anh mau cua du an -> bang tham chieu (chay BiRefNet qua ComfyUI moi lan, ~vai giay).
    guong=True la ban da thu dat 3/3 canh o 768x448 (lan thu 11/09); lat guong chi ra 2 nguoi khi ve 640x352."""
    goc = Image.open(anh).convert("RGB")
    m = mat_na(anh).resize(goc.size)
    ra.parent.mkdir(parents=True, exist_ok=True)
    tam = ra.with_suffix(".tmp.png")
    dung_bang(goc, m, W, H, guong).save(tam)
    tam.replace(ra)
    return ra


def main() -> None:
    guong = "--mot-dang" not in sys.argv
    ts = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(ts) < 2:
        sys.exit(__doc__)
    anh, ra = Path(ts[0]), Path(ts[1])
    W, H = (int(ts[2]), int(ts[3])) if len(ts) >= 4 else (768, 448)
    goc = Image.open(anh).convert("RGB")
    luu = ra.parent / f"{anh.stem}_mat_na.png"          # giu lai: dung lai bo cuc khong phai chay lai BiRefNet
    if luu.exists():
        m = Image.open(luu).convert("L").resize(goc.size)
    else:
        m = mat_na(anh).resize(goc.size)
        ra.parent.mkdir(parents=True, exist_ok=True)
        m.save(luu)
    ra.parent.mkdir(parents=True, exist_ok=True)
    dung_bang(goc, m, W, H, guong).save(ra)
    print(f"-> {ra} ({W}x{H}, {'truoc + lat guong' if guong else 'mot dang'})")


if __name__ == "__main__":
    main()
