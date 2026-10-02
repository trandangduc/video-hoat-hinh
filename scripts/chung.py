"""Thu vien dung chung cho ca 3 buoc cua pipeline.

Giu o day: duong dan, doc kich ban, bang cam xuc -> tham so Chatterbox,
va vai ham in tien do. Ba script 01/02/03 chi con phan viec rieng cua no.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent

VAO = GOC / "vao"
CANH = VAO / "canh"
KICH_BAN = VAO / "kich_ban.json"
GIONG_MAU = VAO / "giong_mau.wav"

RA = GOC / "ra"
TIENG = RA / "tieng"
CLIP = RA / "clip"
VIDEO_CUOI = RA / "video_cuoi.mp4"

MODELS = GOC / "models"
COMFY = GOC / "ComfyUI"
WORKFLOWS = GOC / "workflows"
LOGS = GOC / "logs"

FFMPEG = str(GOC / "cong_cu" / "bin" / "ffmpeg")
FFPROBE = str(GOC / "cong_cu" / "bin" / "ffprobe")

# Cam xuc -> tham so Chatterbox.
#   exaggeration: do "dien cam". 0.5 la mac dinh; cao hon = nhan nha, kich tinh hon.
#   cfg_weight:   cang THAP thi model cang bam theo cam xuc va noi cham lai.
# Cap so nay lay tu khuyen nghi cua Resemble AI: canh kich tinh dung
# exaggeration cao + cfg thap; canh ke chuyen thi nguoc lai.
CAM_XUC = {
    "binh_thuong": (0.5, 0.5),
    "vui":         (0.7, 0.4),
    "buon":        (0.45, 0.6),
    "nhe_nhang":   (0.4, 0.6),
    "hoi_hop":     (0.8, 0.35),
    "cang_thang":  (0.8, 0.35),
    "gian":        (0.9, 0.3),
    "trang_trong": (0.55, 0.55),
}

NEGATIVE_MAC_DINH = (
    "blurry, low quality, distorted face, deformed hands, extra limbs, "
    "watermark, text, oversaturated, static, jpeg artifacts"
)


@dataclass
class Canh:
    id: str
    anh: str
    thoai: str
    cam_xuc: str
    ghi_chu: str
    # Cach lam hinh cho canh nay:
    #   ken_burns = anh tinh troi/zoom cham bang ffmpeg (khong GPU, gan nhu tuc thi)
    #   i2v       = Wan I2V, anh -> chuyen dong that
    #   s2v       = Wan S2V, anh + tieng -> khop mieng (chi khi nhan vat NOI tren hinh)
    kieu: str = "s2v"
    # Canh nay co phai cu may vao NGUOI DAN khong. Neu co thi giu YEN khung
    # hinh: zoom vao mot nguoi dang doc loi binh khong noi len dieu gi, va lam
    # nguoi xem tuong sap co gi do xay ra. Canh khac thi duoc phep chuyen dong.
    nguoi_dan: bool = False
    # Do dai canh theo KICH BAN (timecode [mm:ss-mm:ss] o dang canh).
    # Neu None thi dung do dai tieng (canh co thoai) hay giay_canh_khong_thoai.
    # Canh LTX ("tu ve") dung nay de clip khong duoc ngang hon / ngang tap
    # theo kich ban -- BO NAY la cai giu video khop do dai kich ban.
    giay_du_kien: float | None = None
    # Cu may trong mot segment. Rong = de code tu chia. Moi cu:
    #   {"vung": "toan|mat|than|trai|phai|tren|duoi", "chuyen_dong": "tinh|zoom_vao|..."}
    cu_may: list = field(default_factory=list)

    @property
    def co_thoai(self) -> bool:
        return bool(self.thoai.strip())

    @property
    def duong_anh(self) -> Path:
        return CANH / self.anh

    @property
    def duong_wav(self) -> Path:
        return TIENG / f"{self.id}.wav"

    @property
    def duong_clip(self) -> Path:
        return CLIP / f"{self.id}.mp4"

    def tham_so_giong(self) -> tuple[float, float]:
        return CAM_XUC.get(self.cam_xuc, CAM_XUC["binh_thuong"])


@dataclass
class KichBan:
    ten_video: str
    fps: int
    rong: int
    cao: int
    giay_canh_khong_thoai: float
    phu_de: bool
    kieu_mac_dinh: str = "s2v"
    # Phong cach hinh cho kieu t2v. De trong = dung mac dinh trong 02_hoat_hinh.py
    # (bang trang). Nguoi dung go chuoi rieng o giao dien de doi hoan toan nhan
    # vat / net ve ma khong phai sua code.
    phong_cach_t2v: str = ""
    canh: list[Canh] = field(default_factory=list)

    def tim(self, ma: str) -> Canh | None:
        return next((c for c in self.canh if c.id == ma), None)


def doc_kich_ban(duong: Path | None = None) -> KichBan:
    duong = duong or KICH_BAN
    if not duong.exists():
        loi(f"Khong thay {duong}. Bo kich_ban.json vao thu muc vao/ truoc da.")
    d = json.loads(duong.read_text(encoding="utf-8"))
    c = d.get("cau_hinh", {})
    canh = [
        Canh(
            id=x["id"],
            anh=x.get("anh", ""),
            thoai=x.get("thoai", "") or "",
            cam_xuc=x.get("cam_xuc", "binh_thuong"),
            ghi_chu=x.get("ghi_chu", "") or "",
            kieu=x.get("kieu") or c.get("kieu_mac_dinh") or "s2v",
            nguoi_dan=bool(x.get("nguoi_dan", False)),
            cu_may=x.get("cu_may") or [],
            giay_du_kien=x.get("_giay_du_kien") or x.get("giay_du_kien"),
        )
        for x in d.get("canh", [])
    ]
    return KichBan(
        ten_video=d.get("ten_video", "video"),
        fps=int(c.get("fps", 16)),
        rong=int(c.get("rong", 832)),
        cao=int(c.get("cao", 480)),
        giay_canh_khong_thoai=float(c.get("giay_canh_khong_thoai", 5)),
        phu_de=bool(c.get("phu_de", True)),
        kieu_mac_dinh=c.get("kieu_mac_dinh", "s2v"),
        phong_cach_t2v=(c.get("phong_cach_t2v") or "").strip(),
        canh=canh,
    )


def kiem_kich_ban(kb: KichBan) -> list[str]:
    """Tra ve danh sach van de. Rong = chay duoc."""
    van_de = []
    if not kb.canh:
        van_de.append("Kich ban khong co canh nao.")
    thay = set()
    for c in kb.canh:
        if c.id in thay:
            van_de.append(f"Trung id canh: {c.id}")
        thay.add(c.id)
        if c.kieu == "t2v":
            pass          # t2v ve toan bo tu chu -> khong can anh mau
        elif not c.anh:
            van_de.append(f"{c.id}: thieu ten file anh.")
        elif not c.duong_anh.exists():
            van_de.append(f"{c.id}: khong thay anh {c.duong_anh.relative_to(GOC)}")
        if c.kieu not in ("ken_burns", "i2v", "s2v", "ltx", "t2v"):
            van_de.append(f"{c.id}: kieu '{c.kieu}' khong hop le "
                          f"(ken_burns / i2v / s2v / ltx / t2v)")
        if c.kieu == "s2v" and not c.co_thoai:
            van_de.append(f"{c.id}: kieu s2v nhung khong co thoai — S2V can audio.")
        if c.cam_xuc not in CAM_XUC:
            van_de.append(f"{c.id}: cam xuc '{c.cam_xuc}' khong co trong bang "
                          f"({', '.join(CAM_XUC)})")
    if kb.rong % 16 or kb.cao % 16:
        van_de.append(f"Kich thuoc {kb.rong}x{kb.cao} phai chia het cho 16.")
    return van_de


# ---------------------------------------------------------------- in tien do

_T0 = time.time()


def buoc(tin: str) -> None:
    print(f"\n[{time.time() - _T0:6.1f}s] == {tin}", flush=True)


def noi(tin: str) -> None:
    print(f"[{time.time() - _T0:6.1f}s]    {tin}", flush=True)


def loi(tin: str) -> None:
    print(f"\nLOI: {tin}", file=sys.stderr, flush=True)
    raise SystemExit(1)


# ------------------------------------------------------------------- ffmpeg

def do_dai_wav(duong: Path) -> float:
    ra = subprocess.run(
        [FFPROBE, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(duong)],
        capture_output=True, text=True,
    )
    try:
        return float(ra.stdout.strip())
    except ValueError:
        loi(f"Khong doc duoc do dai {duong}: {ra.stderr.strip()}")
        return 0.0


def so_khung(giay: float, fps: int, toi_da: int = 201, buoc: int = 4) -> int:
    """So khung hop le cho model.

    Wan doi dang 4n+1, LTX-2.5 doi 8n+1. Luon lam tron LEN de khong cat mat
    tieng -- thieu mot khung la cau noi bi cut o cuoi.
    """
    n = int(giay * fps + 0.999)
    n = ((n + buoc - 1) // buoc) * buoc + 1
    return max(buoc + 1, min(n, toi_da))


def vram_dang_ranh(gpu: int = 0) -> int:
    """MiB con trong tren GPU chi dinh. 0 neu khong hoi duoc."""
    try:
        ra = subprocess.run(
            ["nvidia-smi", f"--id={gpu}", "--query-gpu=memory.free",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10)
        return int(ra.stdout.strip().splitlines()[0])
    except Exception:
        return 0


def gpu_dung() -> str:
    """GPU nao pipeline duoc phep dung. Doc CUDA_VISIBLE_DEVICES neu co."""
    return (os.environ.get("CUDA_VISIBLE_DEVICES") or "0").split(",")[0].strip()
