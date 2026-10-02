"""Hang doi viec cua Xuong video — HAI luong ve song song, moi GPU mot luong.

Server chi GHI viec vao ra/xuong/hang_doi.json roi dam bao moi may ve co viec lam thi co tien trinh chay.
Moi may ve (gpu0 -> ComfyUI :8188, gpu1 -> ComfyUI :8189) la mot tien trinh rieng, tu lay viec tiep
theo MA NO LAM DUOC cho toi khi het; tat server hay dong trinh duyet thi viec van chay het. Moi may chi
mot tien trinh (khoa file + file pid rieng).

  CUDA_VISIBLE_DEVICES=0 python cong_cu/hang_doi.py gpu0
  CUDA_VISIBLE_DEVICES=1 python cong_cu/hang_doi.py gpu1

Truoc 11/09/2026 chi co MOT tien trinh (doc giong o GPU1, ve qua ComfyUI GPU0) -> 2 GPU ma canh van ve lan
luot. Hai ComfyUI song song duoc nho tat bo nho ghim (cong_cu/comfy.sh): RAM an danh 40 -> 5 GB moi ban,
toc do ve khong doi (57,1 s vs 58,0 s canh Nhanh 5 giay). Moi tien trinh doc giong (Chatterbox ~3 GB) tren
chinh GPU cua no. Chi bat mot so may: XUONG_MAY=gpu0.

Luat lay viec: merge cua mot du an chi chay khi du an do khong con canh dang ve hay dang cho truoc no;
canh cua du an dang merge thi doi merge xong.
"""
from __future__ import annotations

import fcntl
import json
import os
import subprocess
import sys
import time
import traceback
import urllib.request
from contextlib import contextmanager
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
XUONG = GOC / "ra" / "xuong"
FILE = XUONG / "hang_doi.json"
KHOA = XUONG / "hang_doi.lock"
MAY_VE = {"gpu0": {"gpu": "0", "cong": 8188}, "gpu1": {"gpu": "1", "cong": 8189}}
MAY_BAT = [t for t in os.environ.get("XUONG_MAY", "gpu0,gpu1").split(",") if t in MAY_VE] or ["gpu0"]


@contextmanager
def khoa():
    XUONG.mkdir(parents=True, exist_ok=True)
    with open(KHOA, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


def _pid(ten: str) -> Path:
    return XUONG / f"hang_doi_{ten}.pid"


def doc() -> dict:
    q = {"cho": [], "dang": {}, "xong": []}
    if FILE.exists():
        try:
            q.update(json.loads(FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    d = q.get("dang")
    if not isinstance(d, dict):
        q["dang"] = {}
    elif "loai" in d:                      # dinh dang cu: mot viec dang chay
        q["dang"] = {"gpu0": d}
    return q


def ghi(q: dict) -> None:
    tam = FILE.with_suffix(".tmp")
    tam.write_text(json.dumps(q, ensure_ascii=False, indent=1), encoding="utf-8")
    tam.replace(FILE)


def dang_song(ten: str | None = None) -> bool:
    """May `ten` (hoac bat ky may nao) co tien trinh dang song."""
    for t in ([ten] if ten else list(MAY_VE)):
        try:
            os.kill(int(_pid(t).read_text()), 0)
            return True
        except Exception:
            pass
    return False


def dang_chay(q: dict) -> dict:
    """{ten may: viec} cua cac may con song — viec cua tien trinh da chet giua chung bi bo qua."""
    return {t: v for t, v in (q.get("dang") or {}).items() if v and dang_song(t)}


def _cung(a: dict, b: dict) -> bool:
    return all(b.get(k) == a.get(k) for k in ("loai", "du_an", "canh"))


def them(viec: dict) -> dict:
    """Server goi: them viec (bo qua neu da cho hoac dang chay). Tra ve hang doi moi."""
    with khoa():
        q = doc()
        if not any(_cung(viec, v) for v in q["cho"]) and not any(_cung(viec, v) for v in dang_chay(q).values()):
            q["cho"].append(viec)
        ghi(q)
        return q


def bo(du_an: str, canh: str | None = None) -> dict:
    """Bo cac viec DANG CHO cua mot du an (hoac mot canh)."""
    with khoa():
        q = doc()
        q["cho"] = [v for v in q["cho"] if not (v["du_an"] == du_an and (canh is None or v.get("canh") == canh))]
        ghi(q)
        return q


def _lam_duoc(q: dict, i: int, chay: list[dict]) -> bool:
    v = q["cho"][i]
    if v.get("loai") == "merge":
        return not (any(x.get("du_an") == v["du_an"] for x in chay) or
                    any(x.get("du_an") == v["du_an"] and x.get("loai") == "canh" for x in q["cho"][:i]))
    return not any(x.get("du_an") == v["du_an"] and x.get("loai") == "merge" for x in chay)


def chon_viec(q: dict, them: list[dict] | None = None) -> int | None:
    """Vi tri viec ma mot may ranh nen lam NGAY (None neu khong co viec lam duoc).

    Nhieu kich ban cung luc: chi xet du an CHUA co viec dang chay, lay du an doi LAU NHAT (q["luot"] = luc
    du an duoc nhan viec gan nhat; chua tung thi truoc het) -> 2 du an moi du an giu mot GPU, 3 du an tro
    len xoay vong. Ban dau chi lay "du an dau tien dang nghi" thi A va B thay nhau giu 2 GPU, C doi toi khi
    A, B het viec (kiem thu 11/09 bat duoc). `them`: viec gia dinh dang chay (de dem truoc so viec)."""
    chay = list(dang_chay(q).values()) + list(them or [])
    hop_le = [i for i in range(len(q["cho"])) if _lam_duoc(q, i, chay)]
    if not hop_le:
        return None
    dang_ve = {x.get("du_an") for x in chay}
    luot = q.get("luot") or {}
    nghi = [i for i in hop_le if q["cho"][i]["du_an"] not in dang_ve]
    if nghi:
        return min(nghi, key=lambda i: (luot.get(q["cho"][i]["du_an"], 0), i))
    return hop_le[0]


def so_viec_lay_ngay(q: dict, so_may: int) -> int:
    """Neu co `so_may` may ranh thi bao nhieu may bat dau lam ngay duoc (server dung de biet bat may nao)."""
    cho, gia, n = list(q["cho"]), [], 0
    while n < so_may:
        i = chon_viec({**q, "cho": cho}, gia)
        if i is None:
            break
        gia.append(cho.pop(i))
        n += 1
    return n


def dam_bao_comfy(cfg: dict) -> None:
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{cfg['cong']}/system_stats", timeout=3)
        return
    except Exception:
        pass
    print(f"[hang doi] ComfyUI :{cfg['cong']} chua chay -> bat", flush=True)
    subprocess.run(["bash", str(GOC / "cong_cu" / "comfy.sh"), "len"], check=True,
                   env={**os.environ, "CUDA_VISIBLE_DEVICES": cfg["gpu"], "COMFY_PORT": str(cfg["cong"])})


def main() -> None:
    import model_xuong as MX
    with MX.lease():
        _main_ready()


def _main_ready() -> None:
    ten = sys.argv[1] if len(sys.argv) > 1 else "gpu0"
    if ten not in MAY_VE:
        sys.exit(f"May ve '{ten}' khong co — chon {', '.join(MAY_VE)}")
    cfg = MAY_VE[ten]
    sys.path.insert(0, str(GOC / "cong_cu"))
    import xuong as X
    X.DA.MAY = f"http://127.0.0.1:{cfg['cong']}"                          # moi may ve mot ComfyUI
    X.DA.UNET_CUOI = GOC / "logs" / ("comfy_unet.txt" if cfg["cong"] == 8188 else f"comfy_unet_{cfg['cong']}.txt")
    with khoa():
        if dang_song(ten) and int(_pid(ten).read_text()) != os.getpid():
            print(f"[{ten}] da co tien trinh khac cua may nay.", flush=True)
            return
        _pid(ten).write_text(str(os.getpid()))
    print(f"[{ten}] bat dau, pid {os.getpid()}, ComfyUI :{cfg['cong']}, GPU{cfg['gpu']}", flush=True)
    try:
        dam_bao_comfy(cfg)
    except Exception as e:
        print(f"[{ten}] khong bat duoc ComfyUI :{cfg['cong']}: {e}", flush=True)
        with khoa():
            _pid(ten).unlink(missing_ok=True)
        return
    while True:
        with khoa():
            q = doc()
            i = chon_viec(q)
            if i is None:
                q["dang"].pop(ten, None)
                ghi(q)
                _pid(ten).unlink(missing_ok=True)   # xoa TRONG khoa: server them viec sau do se thay can bat lai
                print(f"[{ten}] het viec lam duoc", flush=True)
                return
            viec = q["cho"].pop(i)
            q["dang"][ten] = {**viec, "may": ten, "bat_dau": time.time()}
            con = {x["du_an"] for x in q["cho"]} | {viec["du_an"]}           # chi giu du an con viec
            q["luot"] = {k: v for k, v in (q.get("luot") or {}).items() if k in con}
            q["luot"][viec["du_an"]] = time.time()
            ghi(q)
        duong = XUONG / viec["du_an"] / "du_an.json"
        ket = {**viec, "may": ten, "ok": True, "loi": "", "luc": time.time()}
        print(f"[{ten}] -> {viec}", flush=True)
        try:
            if viec["loai"] == "canh":
                X.tao_canh(duong, viec["canh"])
            elif viec["loai"] == "merge":
                X.merge(duong)
        except KeyboardInterrupt:
            raise
        except BaseException as e:           # ca SystemExit do ffmpeg loi
            ket.update(ok=False, loi=str(e)[:600])
            traceback.print_exc()
        with khoa():
            q = doc()
            q["dang"].pop(ten, None)
            q["xong"] = (q.get("xong") or [])[-49:] + [ket]
            ghi(q)


if __name__ == "__main__":
    main()
