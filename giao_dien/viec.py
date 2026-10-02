"""Chay viec NEN, song sot qua ca viec tat server.

Cach cu (Popen la con cua server + log trong deque RAM) co hai cho chet:
tat server la tien trinh chet theo, va khoi dong lai la mat sach log. Nguoi
dung muon bam chay roi dong may, sang hom sau mo len thay video da xong --
nen viec phai roi han khoi server.

Ba thay doi:
  1. `start_new_session=True` -> tien trinh sang phien rieng, khong nhan
     SIGHUP khi server tat.
  2. stdout ghi THANG ra file trong logs/viec/, khong qua ong dan cua server.
  3. Trang thai nam trong logs/viec/hien_tai.json -> server khoi dong lai thi
     doc file do va noi lai voi viec dang chay.

Ma thoat khong lay duoc bang wait() (viec khong con la con cua ta), nen boc
lenh trong `bash -c '...; echo $? > <file>.ma'`. File .ma xuat hien = da xong.
"""
from __future__ import annotations

import json
import os
import shlex
import signal
import subprocess
import time
from pathlib import Path


class ViecNen:
    def __init__(self, thu_muc: Path, goc: Path) -> None:
        self.tm = thu_muc
        self.tm.mkdir(parents=True, exist_ok=True)
        self.goc = goc
        self.trang_thai = self.tm / "hien_tai.json"

    # ------------------------------------------------------------- doc/ghi

    def _doc(self) -> dict | None:
        if not self.trang_thai.exists():
            return None
        try:
            return json.loads(self.trang_thai.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _ghi(self, d: dict) -> None:
        self.trang_thai.write_text(json.dumps(d, ensure_ascii=False, indent=1),
                                   encoding="utf-8")

    # ------------------------------------------------------------ tra loi

    @staticmethod
    def _con_song(pid: int) -> bool:
        try:
            os.kill(pid, 0)
        except (ProcessLookupError, ValueError):
            return False
        except PermissionError:
            return True          # ton tai nhung khac chu -> van coi la song
        return True

    def _ma_thoat(self, d: dict) -> int | None:
        p = Path(d["ma_file"])
        if not p.exists():
            return None
        try:
            return int(p.read_text().strip() or 0)
        except Exception:
            return 0

    def anh(self) -> dict:
        """Trang thai hien tai, doc tu dia nen dung ca sau khi server khoi dong lai."""
        d = self._doc()
        if not d:
            return {"co": False, "dang_chay": False, "ten": "", "ma_thoat": None}
        ma = self._ma_thoat(d)
        song = ma is None and self._con_song(d["pid"])
        # Tien trinh bien mat ma khong kip ghi file .ma (bi kill -9, may sap
        # nguon) -> coi nhu that bai thay vi treo mai o trang thai "dang chay".
        if ma is None and not song:
            ma = -1
        return {
            "co": True,
            "ten": d.get("ten", ""),
            "dang_chay": song,
            "ma_thoat": ma,
            "pid": d["pid"],
            "bat_dau": d.get("bat_dau", 0),
            "giay": round(time.time() - d.get("bat_dau", time.time())),
            "lenh": d.get("lenh", ""),
            "kich_ban": d.get("kich_ban", ""),
        }

    @property
    def dang_chay(self) -> bool:
        return bool(self.anh().get("dang_chay"))

    # --------------------------------------------------------------- chay

    def chay(self, ten: str, lenh: list[str], kich_ban: str = "") -> dict:
        if self.dang_chay:
            raise RuntimeError(f"Dang chay '{self.anh()['ten']}', doi xong da.")
        moc = time.strftime("%Y%m%d_%H%M%S")
        log = self.tm / f"{moc}_{ten}.log"
        ma_file = self.tm / f"{moc}_{ten}.ma"
        boc = f"{shlex.join(lenh)}; echo $? > {shlex.quote(str(ma_file))}"

        moi = {**os.environ,
               "CUDA_VISIBLE_DEVICES": os.environ.get("CUDA_VISIBLE_DEVICES", "0"),
               "PYTHONUNBUFFERED": "1"}
        with open(log, "w", encoding="utf-8") as f:
            f.write(f"$ {shlex.join(lenh)}\n")
            f.flush()
            p = subprocess.Popen(
                ["bash", "-c", boc], cwd=str(self.goc), env=moi,
                stdout=f, stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True)      # <- roi khoi server
        d = {"ten": ten, "pid": p.pid, "bat_dau": time.time(),
             "log": str(log), "ma_file": str(ma_file),
             "lenh": shlex.join(lenh), "kich_ban": kich_ban}
        self._ghi(d)
        return self.anh()

    def dung(self) -> bool:
        d = self._doc()
        if not d or not self.dang_chay:
            return False
        # Giet ca NHOM tien trinh: viec la `bash -c` boc python, ma python lai
        # de ra tien trinh con. Giet moi bash thi python thanh mo coi chay tiep.
        try:
            os.killpg(os.getpgid(d["pid"]), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(d["pid"], signal.SIGTERM)
            except ProcessLookupError:
                return False
        return True

    # ---------------------------------------------------------------- log

    def doc_log(self, tu: int = 0) -> tuple[list[str], int]:
        """Cac dong tu byte `tu` tro di, kem moc byte moi.

        Tra ve moc theo BYTE chu khong theo so dong: file log co the rat dai,
        dem lai tu dau moi lan hoi la phi. Doc tu offset thi luon O(phan moi).
        """
        d = self._doc()
        if not d:
            return [], 0
        p = Path(d["log"])
        if not p.exists():
            return [], 0
        co = p.stat().st_size
        if tu > co:              # viec moi, file ngan hon -> doc lai tu dau
            tu = 0
        if tu == co:
            return [], co
        with open(p, "rb") as f:
            f.seek(tu)
            tho = f.read()
        # Bo phan duoi cung neu chua tron dong (viec dang ghi do)
        cuoi = tho.rfind(b"\n")
        if cuoi == -1:
            return [], tu
        dung = tho[:cuoi].decode("utf-8", "replace")
        moc = tu + cuoi + 1
        ra = []
        for dong in dung.split("\n"):
            if "\r" in dong:      # tqdm ghi de bang \r -> giu manh cuoi
                dong = dong.rsplit("\r", 1)[-1]
            if dong.strip():
                ra.append(dong)
        return ra, moc

    def don_log_cu(self, giu: int = 40) -> None:
        cac = sorted(self.tm.glob("*.log"), key=lambda p: p.stat().st_mtime)
        for p in cac[:-giu]:
            p.unlink(missing_ok=True)
            p.with_suffix(".ma").unlink(missing_ok=True)
