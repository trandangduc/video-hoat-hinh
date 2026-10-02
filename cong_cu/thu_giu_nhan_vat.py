"""Kiem thu dau-cuoi kieu anh "Giu nhan vat (bang tham chieu)" cua Xuong QUA API.

  .venv/bin/python cong_cu/thu_giu_nhan_vat.py [http://127.0.0.1:7899]
  -> logs/thu_giu_nhan_vat.json

  1. Tao du an, tai anh mau -> doi may doc anh VA dung xong bang tham chieu (co_bang).
  2. 3 canh kieu tham_chieu: tuyet 5 giay · ban viet co loi doc · phong luu tru 10 giay (thu gioi han).
  3. Tao het -> kiem tung clip (che_do tham_chieu, 1536x896, du do dai).
  4. Merge -> video_moi.
  5. Chuyen Chuan/Nhanh: canh tham_chieu KHONG bi coi la khac che do, "Tao het" khong xep ve lai.
"""
from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import thu_xuong_dau_cuoi as E  # noqa: E402  (api, cho, ghi, kiem, kich_thuoc, the_clip, theo_ram)

E.URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:7899"
E.LOG = GOC / "logs" / "thu_giu_nhan_vat.json"
E.KQ.clear()
E.KQ.update({"bat_dau": time.strftime("%Y-%m-%d %H:%M:%S"), "buoc": [], "ram_trong_thap_nhat_gb": None})
CANH = [
    {"prompt": "The character walks through deep snow in a mountain pass at dawn, leaving footprints; slow tracking shot",
     "loi_doc": "", "giay": 5, "anh": "tham_chieu"},
    {"prompt": "The character sits at an old wooden desk writing in a notebook under a warm desk lamp, frowning; slow push-in",
     "loi_doc": "Every night he wrote down what he had seen in the mountains.", "giay": 5, "anh": "tham_chieu"},
    {"prompt": "The character stands in a dusty archive room and points at a large hand-drawn map on the wall; slow pan",
     "loi_doc": "", "giay": 10, "anh": "tham_chieu"},
]


def main() -> None:
    dung = threading.Event()
    threading.Thread(target=E.theo_ram, args=(dung,), daemon=True).start()
    da = E.api("POST", "/api/xuong", {"ten": "Thử giữ nhân vật — nón lá"})
    id_ = da["id"]
    D = GOC / "ra" / "xuong" / id_
    E.KQ["du_an"] = id_
    E.ghi("tao du an", id=id_)

    r = subprocess.run(["curl", "-sf", "-F", f"file=@{GOC / 'vao/canh/canh_01.png'}",
                        f"{E.URL}/api/xuong/{id_}/tep/anh_mau"], capture_output=True, text=True)
    E.kiem(r.returncode == 0, f"tai anh mau loi: {r.stderr[:200]}")
    da = E.cho(id_, lambda d: not d.get("dang_doc_anh"), 900, 3)
    E.kiem(da and da.get("co_bang"), f"khong dung duoc bang tham chieu: {da and da.get('loi_doc_anh')}")
    E.ghi("anh mau + bang tham chieu", mo_ta=da["mo_ta_anh"], loi=da.get("loi_doc_anh"))

    da = E.api("PUT", f"/api/xuong/{id_}", {"phong_cach": "flat 2D cartoon animation, thick black outlines, flat saturated colours",
                                             "che_do": "nhanh", "canh": CANH})
    ids = [c["id"] for c in da["canh"]]
    t0 = time.time()
    E.api("POST", f"/api/xuong/{id_}/tao-het")
    da = E.cho(id_, E.xong_het(ids), 3000)
    E.kiem(da, "qua 50 phut chua tao xong")
    loi = {i: da["trang_thai_canh"][i]["loi"] for i in ids if da["trang_thai_canh"][i]["trang_thai"] == "loi"}
    E.kiem(not loi, f"canh loi: {loi}")
    the = {i: E.the_clip(D, i) for i in ids}
    for i, t in the.items():
        E.kiem(t["che_do"] == "tham_chieu", f"canh {i} khong ve bang bang tham chieu: {t}")
        E.kiem(t["kich_thuoc"] == (1536, 896), f"canh {i} sai kich thuoc: {t}")
        E.kiem(t["dai_mp4"] + 0.05 >= t["giay"], f"canh {i} ngan hon so giay can: {t}")
    E.ghi("tao het — GIU NHAN VAT", tong_giay=round(time.time() - t0), canh=the)

    E.api("POST", f"/api/xuong/{id_}/merge")
    da = E.cho(id_, lambda d: d["merge"]["trang_thai"] is None and d["hang_doi"]["cho_cua_du_an"] == 0, 900, 5)
    E.kiem(da and da["co_video"] and da["video_moi"] and not da["merge"]["loi"], f"merge loi: {da and da['merge']}")
    E.ghi("merge", giay_video=da["giay_video"], kich_thuoc=E.kich_thuoc(D / "video.mp4"))

    da = E.api("PUT", f"/api/xuong/{id_}", {"che_do": "chuan"})
    tt = da["trang_thai_canh"]
    E.kiem(all(tt[i]["trang_thai"] == "xong" and not tt[i]["khac_che_do"] for i in ids), f"doi che do lam sai canh tham_chieu: {tt}")
    da = E.api("POST", f"/api/xuong/{id_}/tao-het")
    E.kiem(da["hang_doi"]["cho_cua_du_an"] == 0 and not da["hang_doi"]["dang"], f"Tao het xep ve lai canh tham_chieu: {da['hang_doi']}")
    E.ghi("doi Chuan khong ve lai", video_moi=da["video_moi"])

    dung.set()
    E.KQ["ket_qua"] = "OK"
    E.ghi("XONG", ram_trong_thap_nhat_gb=E.KQ["ram_trong_thap_nhat_gb"])


if __name__ == "__main__":
    main()
