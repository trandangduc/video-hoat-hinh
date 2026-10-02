"""Kiem thu dau-cuoi: NHAP KICH BAN .docx + MAY VIET PROMPT + VE SONG SONG canh cung du an, QUA API.

  .venv/bin/python cong_cu/thu_nhap_kich_ban.py ["New Microsoft Word Document.docx"]
  -> logs/thu_nhap_kich_ban.json

  1. Tao du an (Nhanh), nhap file .docx -> dung so canh, ten du an lay tu file.
  2. Trong luc may viet prompt: gia lap trang TU LUU voi prompt trong (trang cu) -> prompt may viet khong mat.
  3. Doi viet xong: moi canh co loi doc deu co prompt (prompt_tu_dong).
  4. Them 1 canh CHI co loi doc, bam Tao -> may viet prompt roi tu xep ve.
  5. Bam Tao 4 canh dau -> 2 canh CUNG du an ve cung luc tren 2 GPU.
"""
from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(GOC / "cong_cu"))
import hang_doi as HD            # noqa: E402
import thu_xuong_dau_cuoi as E   # noqa: E402

MA = (GOC / "logs" / "ma_chia.txt").read_text().strip() if (GOC / "logs" / "ma_chia.txt").exists() else ""
TEP = GOC / (sys.argv[1] if len(sys.argv) > 1 else "New Microsoft Word Document.docx")
E.URL = "http://127.0.0.1:7899"
E.LOG = GOC / "logs" / "thu_nhap_kich_ban.json"
E.KQ.clear()
E.KQ.update({"bat_dau": time.strftime("%Y-%m-%d %H:%M:%S"), "buoc": [], "ram_trong_thap_nhat_gb": None, "dong_thoi_gian": []})


def duoi_ma(path: str) -> str:
    return path + (("&" if "?" in path else "?") + f"ma={MA}" if MA else "")


def api(method: str, path: str, data: dict | None = None, timeout: int = 60) -> dict:
    req = urllib.request.Request(E.URL + duoi_ma(path), method=method, headers={"Content-Type": "application/json"},
                                 data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


E.api = api


def theo_hang_doi(dung: threading.Event, id_: str) -> None:
    truoc = None
    while not dung.is_set():
        chay = {t: v.get("canh") for t, v in HD.dang_chay(HD.doc()).items() if v.get("du_an") == id_}
        if chay != truoc:
            E.KQ["dong_thoi_gian"].append({"luc": time.strftime("%H:%M:%S"), "chay": chay})
            print(f"[{time.strftime('%H:%M:%S')}] dang ve {chay}", flush=True)
            truoc = chay
        time.sleep(2)


def main() -> None:
    dung = threading.Event()
    threading.Thread(target=E.theo_ram, args=(dung,), daemon=True).start()
    da = api("POST", "/api/xuong", {"ten": "Dự án mới"})
    id_ = da["id"]
    api("PUT", f"/api/xuong/{id_}", {"che_do": "nhanh"})
    E.KQ["du_an"] = id_

    t0 = time.time()
    r = subprocess.run(["curl", "-sf", "-F", f"file=@{TEP}", "-F", "kieu=thay", "-F", "anh=khong",
                        E.URL + duoi_ma(f"/api/xuong/{id_}/nhap-kich-ban")], capture_output=True, text=True)
    E.kiem(r.returncode == 0, f"nhap kich ban loi: {r.stdout[:300]} {r.stderr[:200]}")
    da = json.loads(r.stdout)
    so = da["nhap"]["so_canh"]
    E.kiem(so == len(da["canh"]) and so > 0, f"so canh sai: {da['nhap']}")
    E.ghi("nhap kich ban", so_canh=so, tong_giay=da["nhap"]["tong_giay"], ten=da["ten"],
          muc=list(dict.fromkeys(c.get("muc") for c in da["canh"])))

    # trang cu tu luu voi prompt trong trong khi may dang viet
    time.sleep(12)
    cu = [{k: c.get(k) for k in ("id", "loi_doc", "giay", "anh", "muc")} | {"prompt": ""} for c in da["canh"]]
    da2 = api("PUT", f"/api/xuong/{id_}", {"canh": cu})
    da_viet = sum(1 for c in da2["canh"] if (c.get("prompt") or "").strip())
    E.ghi("gia lap trang tu luu voi prompt trong", prompt_con_giu=da_viet, dang_viet=da2.get("dang_viet_prompt"))

    da = E.cho(id_, lambda d: not d.get("dang_viet_prompt"), 1500, 5)
    E.kiem(da, "qua 25 phut chua viet xong prompt")
    thieu = [c["id"] for c in da["canh"] if (c.get("loi_doc") or "").strip() and not (c.get("prompt") or "").strip()]
    E.kiem(not thieu, f"con {len(thieu)} canh chua co prompt; loi: {da.get('loi_viet_prompt')}")
    E.ghi("may viet xong prompt", giay=round(time.time() - t0), so_tu_dong=sum(1 for c in da["canh"] if c.get("prompt_tu_dong")),
          vi_du=[(c["loi_doc"][:50], c["prompt"]) for c in da["canh"][:3]])

    # canh chi co loi doc -> bam Tao -> may viet prompt roi tu xep ve
    them = [{k: c.get(k) for k in ("id", "prompt", "loi_doc", "giay", "anh", "muc")} for c in da["canh"][:4]]
    them.append({"id": "", "prompt": "", "loi_doc": "The mountain still keeps its final answer.", "giay": 5, "anh": "khong"})
    da = api("PUT", f"/api/xuong/{id_}", {"canh": them})
    ids = [c["id"] for c in da["canh"]]
    threading.Thread(target=theo_hang_doi, args=(dung, id_), daemon=True).start()
    t1 = time.time()
    for cid in ids:
        api("POST", f"/api/xuong/{id_}/canh/{cid}/tao")
    da = E.cho(id_, lambda d: E.xong_het(ids)(d) and not any(c.get("tao_sau_viet") for c in d["canh"]), 2400, 5)
    E.kiem(da, "qua 40 phut chua ve xong 5 canh")
    loi = {i: da["trang_thai_canh"][i]["loi"][:200] for i in ids if da["trang_thai_canh"][i]["trang_thai"] == "loi"}
    E.kiem(not loi, f"canh loi: {loi}")
    E.kiem(da["canh"][4].get("prompt_tu_dong"), f"canh chi co loi doc khong duoc viet prompt: {da['canh'][4]}")
    the = {i: E.the_clip(GOC / "ra/xuong" / id_, i) for i in ids}
    cung_luc = [x for x in E.KQ["dong_thoi_gian"] if len(x["chay"]) == 2]
    E.kiem(cung_luc, "khong luc nao 2 canh cung du an ve cung luc")
    tong_ve = round(sum(t["giay_render"] for t in the.values()))
    E.ghi("ve 5 canh cung du an", tong_thuc=round(time.time() - t1), tong_ve=tong_ve,
          tang_toc=round(tong_ve / max(1, time.time() - t1), 2), canh=the, luc_2_canh=cung_luc[0], canh5_prompt=da["canh"][4]["prompt"])
    dung.set()
    E.KQ["ket_qua"] = "OK"
    E.ghi("XONG", ram_trong_thap_nhat_gb=E.KQ["ram_trong_thap_nhat_gb"])


if __name__ == "__main__":
    main()
