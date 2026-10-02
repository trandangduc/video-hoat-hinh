"""Tao tai khoan dang nhap + key video cho MAY MOI (repo khong mang theo .bao_mat/).

  .venv/bin/python cong_cu/tao_admin.py              # hoi mat khau
  MAT_KHAU=... .venv/bin/python cong_cu/tao_admin.py # khong hoi (dung trong script)

- .bao_mat/admin.json: ten + scrypt(mat khau), dung dinh dang giao_dien/bao_mat.py doc.
  Chay lai = doi mat khau.
- .bao_mat/video.key: 32 byte ngau nhien Base64. KHONG BAO GIO ghi de key da co
  (mat key cu = mat het video .brd cu). May cu da co key thi chep file key sang.
"""
from __future__ import annotations
import base64
import getpass
import json
import os
import secrets
import sys
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "giao_dien"))
from bao_mat import PRIVATE, password_hash  # noqa: E402


def ghi_rieng(p: Path, noi_dung: str):
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="ascii") as f:
        f.write(noi_dung)
    os.chmod(p, 0o600)


def main():
    PRIVATE.mkdir(mode=0o700, exist_ok=True)
    os.chmod(PRIVATE, 0o700)

    ten = os.environ.get("TEN", "admin")
    mk = os.environ.get("MAT_KHAU") or getpass.getpass(f"Mat khau cho '{ten}': ")
    if len(mk) < 8:
        sys.exit("Mat khau qua ngan (it nhat 8 ky tu).")
    salt = secrets.token_bytes(16)
    ghi_rieng(PRIVATE / "admin.json", json.dumps(
        {"username": ten, "salt": salt.hex(), "hash": password_hash(mk, salt)}))
    print(f"da ghi {PRIVATE / 'admin.json'} (tai khoan '{ten}')")

    key = PRIVATE / "video.key"
    if key.exists():
        print(f"giu nguyen key cu: {key}")
    else:
        ghi_rieng(key, base64.b64encode(secrets.token_bytes(32)).decode() + "\n")
        print(f"da tao key moi: {key}  -> SAO LUU file nay, mat la khong giai ma duoc video")


if __name__ == "__main__":
    main()
