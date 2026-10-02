"""Kiem thu dau-cuoi Xuong video QUA API — lam dung nhu nguoi dung bam tren giao dien.

  .venv/bin/python cong_cu/thu_xuong_dau_cuoi.py [http://127.0.0.1:7899]
  -> logs/thu_xuong_dau_cuoi.json (tung buoc, so giay ve that, RAM trong thap nhat)

Kich ban:
  1. Tao du an, tai anh mau (vao/canh/canh_01.png), doi may doc anh.
  2. Che do NHANH, 3 canh: t2v 5 giay · co loi doc + ta nhan vat · anh lam khung mo dau 4 giay.
  3. Tao het -> doi xong -> kiem tung clip (1280x704, che_do, do dai).
  4. Merge -> video_moi.
  5. Chuyen CHUAN: canh van 'xong' + khac_che_do, video van moi.
  6. Ve lai canh 1 o CHUAN -> kiem doi model (ComfyUI /free) khong tran RAM.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import lam_video_collage as LV  # noqa: E402

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7899"
LOG = GOC / "logs" / "thu_xuong_dau_cuoi.json"
KQ: dict = {"bat_dau": time.strftime("%Y-%m-%d %H:%M:%S"), "buoc": [], "ram_trong_thap_nhat_gb": None}
CANH = [
    {"prompt": "an old photograph pinned among torn notebook pages showing six hikers in heavy winter jackets "
               "walking through deep snow toward the camera, slow push-in",
     "loi_doc": "", "giay": 5, "anh": "khong"},
    {"prompt": "the man studies an old paper map spread on a wooden desk under a warm lamp, slow push-in",
     "loi_doc": "On the night of February first, nineteen fifty-nine, nine hikers left their tent and never came back.",
     "giay": 5, "anh": "mo_ta"},
    {"prompt": "the man points at the map of Dyatlov Pass on the wall and turns his head to the camera, slow push-in",
     "loi_doc": "", "giay": 4, "anh": "khung_dau"},
]


def api(method: str, path: str, data: dict | None = None, timeout: int = 60) -> dict:
    req = urllib.request.Request(URL + path, method=method, headers={"Content-Type": "application/json"},
                                 data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def ghi(buoc: str, **kw) -> None:
    KQ["buoc"].append({"buoc": buoc, "luc": time.strftime("%H:%M:%S"), **kw})
    print(f"[{time.strftime('%H:%M:%S')}] {buoc} {json.dumps(kw, ensure_ascii=False)[:400]}", flush=True)
    LOG.write_text(json.dumps(KQ, ensure_ascii=False, indent=1), encoding="utf-8")


def kiem(dk, thong_bao: str) -> None:
    if not dk:
        KQ["ket_qua"] = "THAT BAI"
        ghi("THAT BAI", loi=thong_bao)
        sys.exit(1)


def cho(id_: str, dieu_kien, toi_da: float, moi: float = 10) -> dict | None:
    t = time.time()
    while time.time() - t < toi_da:
        try:
            da = api("GET", f"/api/xuong/{id_}")
            if dieu_kien(da):
                return da
        except Exception as e:           # server ban tam thoi — thu lai
            print("  (loi goi api, thu lai)", e, flush=True)
        time.sleep(moi)
    return None


def xong_het(ids: list[str]):
    def dk(d: dict) -> bool:
        tt = d["trang_thai_canh"]
        return (all(tt[i]["trang_thai"] in ("xong", "loi") for i in ids)
                and not d["hang_doi"]["dang"] and d["hang_doi"]["cho_cua_du_an"] == 0)
    return dk


def kich_thuoc(mp4: Path) -> tuple[int, int]:
    r = subprocess.run([LV.FF, "-hide_banner", "-i", str(mp4)], capture_output=True, text=True)
    m = re.search(r"Video:.*?, (\d{3,4})x(\d{3,4})", r.stderr)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def theo_ram(dung: threading.Event) -> None:
    thap = None
    while not dung.is_set():
        for dong in open("/proc/meminfo"):
            if dong.startswith("MemAvailable:"):
                gb = int(dong.split()[1]) / 1048576
                thap = gb if thap is None else min(thap, gb)
                KQ["ram_trong_thap_nhat_gb"] = round(thap, 1)
        time.sleep(2)


def the_clip(D: Path, cid: str) -> dict:
    cj = json.loads((D / "clip" / f"{cid}.json").read_text(encoding="utf-8"))
    mp4 = D / "clip" / f"{cid}.mp4"
    return {"che_do": cj.get("che_do"), "khung": cj.get("khung"), "giay": cj.get("giay"),
            "giay_render": cj.get("giay_render"), "kich_thuoc": kich_thuoc(mp4), "dai_mp4": round(LV.do_dai(mp4), 2)}


def main() -> None:
    dung = threading.Event()
    threading.Thread(target=theo_ram, args=(dung,), daemon=True).start()

    da = api("POST", "/api/xuong", {"ten": "Thử đầu–cuối — Nhanh/Chuẩn"})
    id_ = da["id"]
    D = GOC / "ra" / "xuong" / id_
    KQ["du_an"] = id_
    ghi("tao du an", id=id_, che_do_mac_dinh=da.get("che_do"))

    r = subprocess.run(["curl", "-sf", "-F", f"file=@{GOC / 'vao/canh/canh_01.png'}",
                        f"{URL}/api/xuong/{id_}/tep/anh_mau"], capture_output=True, text=True)
    kiem(r.returncode == 0, f"tai anh mau loi: {r.stderr[:200]}")
    da = cho(id_, lambda d: not d.get("dang_doc_anh"), 600, 3)
    kiem(da and (da.get("mo_ta_anh") or "").strip(), f"doc anh mau loi: {da and da.get('loi_doc_anh')}")
    ghi("doc anh mau", mo_ta=da["mo_ta_anh"])

    # --- NHANH
    da = api("PUT", f"/api/xuong/{id_}", {"che_do": "nhanh", "canh": CANH})
    kiem(da.get("che_do") == "nhanh", "server khong luu che_do")
    ids = [c["id"] for c in da["canh"]]
    kiem(all(da["trang_thai_canh"][i]["trang_thai"] == "chua_tao" for i in ids), "canh moi khong o trang thai chua_tao")
    t0 = time.time()
    api("POST", f"/api/xuong/{id_}/tao-het")
    da = cho(id_, xong_het(ids), 3600)
    kiem(da, "qua 60 phut chua tao xong")
    loi = {i: da["trang_thai_canh"][i]["loi"] for i in ids if da["trang_thai_canh"][i]["trang_thai"] == "loi"}
    kiem(not loi, f"canh loi: {loi}")
    the = {i: the_clip(D, i) for i in ids}
    for i, t in the.items():
        kiem(t["che_do"] == "nhanh", f"canh {i} khong ve o che do nhanh: {t}")
        kiem(t["kich_thuoc"] == (1280, 704), f"canh {i} sai kich thuoc: {t}")
        kiem(t["dai_mp4"] + 0.05 >= t["giay"], f"canh {i} ngan hon so giay can: {t}")
    ghi("tao het — NHANH", tong_giay=round(time.time() - t0), canh=the,
        giay_tieng=da["trang_thai_canh"][ids[1]]["giay_tieng"])

    api("POST", f"/api/xuong/{id_}/merge")
    da = cho(id_, lambda d: d["merge"]["trang_thai"] is None and d["hang_doi"]["cho_cua_du_an"] == 0, 900, 5)
    kiem(da and da["co_video"] and da["video_moi"] and not da["merge"]["loi"], f"merge loi: {da and da['merge']}")
    ghi("merge", giay_video=da["giay_video"], mb=da["mb_video"], kich_thuoc=kich_thuoc(D / "video.mp4"))

    # --- chuyen CHUAN: khong duoc lam hong ban da ve
    da = api("PUT", f"/api/xuong/{id_}", {"che_do": "chuan"})
    tt = da["trang_thai_canh"]
    kiem(all(tt[i]["trang_thai"] == "xong" and tt[i]["khac_che_do"] and tt[i]["che_do"] == "nhanh" for i in ids),
         f"doi che do lam sai trang thai: {tt}")
    kiem(da["video_moi"], "doi che do lam video thanh cu")
    ghi("chuyen CHUAN", khac_che_do=[tt[i]["khac_che_do"] for i in ids], video_moi=da["video_moi"])

    # --- ve lai canh 1 o CHUAN: doi model distilled -> dev qua /free
    t0 = time.time()
    api("POST", f"/api/xuong/{id_}/canh/{ids[0]}/tao")
    da = cho(id_, xong_het([ids[0]]), 2400)
    kiem(da, "ve lai chuan qua 40 phut")
    s = da["trang_thai_canh"][ids[0]]
    kiem(s["trang_thai"] == "xong" and not s["khac_che_do"], f"ve lai chuan loi: {s}")
    t1 = the_clip(D, ids[0])
    kiem(t1["che_do"] == "chuan" and t1["kich_thuoc"] == (1280, 704), f"clip chuan sai: {t1}")
    unet = (GOC / "logs" / "comfy_unet.txt").read_text().strip()
    ghi("ve lai canh 1 — CHUAN", tong_giay=round(time.time() - t0), canh=t1, unet_cuoi=unet,
        video_moi=da["video_moi"], con_khac=[da["trang_thai_canh"][i]["khac_che_do"] for i in ids])
    kiem(not da["video_moi"], "canh ve lai roi ma video van bao moi")

    dung.set()
    KQ["ket_qua"] = "OK"
    ghi("XONG", ram_trong_thap_nhat_gb=KQ["ram_trong_thap_nhat_gb"])


if __name__ == "__main__":
    main()
