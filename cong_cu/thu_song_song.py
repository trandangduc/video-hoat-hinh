"""Kiem thu ve SONG SONG tren 2 GPU voi NHIEU du an cung luc, QUA API (nhu nguoi dung bam tren web).

  .venv/bin/python cong_cu/thu_song_song.py
  -> logs/thu_song_song.json

  1. Tao 2 du an (A, B), moi du an 2 canh Nhanh 5 giay, bam Tao het cho A roi B ngay lap tuc.
  2. Moi 3 giay ghi lai may nao dang ve canh nao: phai co luc 2 canh chay cung luc, va luc dau phai la
     MOI DU AN MOT GPU (khong de A giu ca 2 GPU trong khi B cho).
  3. Doi xong het: so tong thoi gian thuc voi tong thoi gian ve cua 4 canh -> muc tang toc.
  4. Merge ca 2 cung luc -> 2 video moi.
"""
from __future__ import annotations

import json
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
E.URL = "http://127.0.0.1:7899"
E.LOG = GOC / "logs" / "thu_song_song.json"
E.KQ.clear()
E.KQ.update({"bat_dau": time.strftime("%Y-%m-%d %H:%M:%S"), "buoc": [], "ram_trong_thap_nhat_gb": None, "dong_thoi_gian": []})


def api(method: str, path: str, data: dict | None = None, timeout: int = 60) -> dict:
    """Nhu E.api nhung kem ma vao (server dang chia se, CHIA=1)."""
    if MA:
        path += ("&" if "?" in path else "?") + f"ma={MA}"
    req = urllib.request.Request(E.URL + path, method=method, headers={"Content-Type": "application/json"},
                                 data=json.dumps(data).encode() if data is not None else None)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


E.api = api     # E.cho goi E.api -> dung ban co ma


def tao_du_an(ten: str, canh: list[str]) -> tuple[str, list[str]]:
    da = api("POST", "/api/xuong", {"ten": ten})
    da = api("PUT", f"/api/xuong/{da['id']}", {
        "che_do": "nhanh", "phong_cach": "flat 2D cartoon animation, thick black outlines, flat saturated colours",
        "canh": [{"prompt": p, "loi_doc": "", "giay": 5, "anh": "khong"} for p in canh]})
    return da["id"], [c["id"] for c in da["canh"]]


def theo_hang_doi(dung: threading.Event) -> None:
    truoc = None
    while not dung.is_set():
        q = HD.doc()
        chay = {t: (v["du_an"][-4:], v.get("loai"), v.get("canh")) for t, v in HD.dang_chay(q).items()}
        if chay != truoc:
            E.KQ["dong_thoi_gian"].append({"luc": time.strftime("%H:%M:%S"), "chay": chay, "cho": len(q["cho"])})
            print(f"[{time.strftime('%H:%M:%S')}] dang chay {chay} | cho {len(q['cho'])}", flush=True)
            truoc = chay
        time.sleep(3)


def main() -> None:
    dung = threading.Event()
    threading.Thread(target=E.theo_ram, args=(dung,), daemon=True).start()
    A, ca = tao_du_an("Song song A — tuyết", [
        "a man in a conical straw hat walks through deep snow at dawn, slow tracking shot",
        "the man builds a small campfire in the snow at dusk, slow push-in"])
    B, cb = tao_du_an("Song song B — biển", [
        "a red fishing boat sails across a calm turquoise sea at noon, slow pan",
        "a lighthouse on a rocky cliff with waves crashing below, slow push-in"])
    E.ghi("tao 2 du an", A=A, B=B)
    threading.Thread(target=theo_hang_doi, args=(dung,), daemon=True).start()
    t0 = time.time()
    api("POST", f"/api/xuong/{A}/tao-het")
    api("POST", f"/api/xuong/{B}/tao-het")
    xong = lambda id_, ids: E.cho(id_, E.xong_het(ids), 3000, 5)
    da_a, da_b = xong(A, ca), xong(B, cb)
    E.kiem(da_a and da_b, "qua 50 phut chua xong")
    tong_thuc = round(time.time() - t0)
    the = {**{f"A{i + 1}": E.the_clip(GOC / "ra/xuong" / A, c) for i, c in enumerate(ca)},
           **{f"B{i + 1}": E.the_clip(GOC / "ra/xuong" / B, c) for i, c in enumerate(cb)}}
    for k, t in the.items():
        E.kiem(t["kich_thuoc"] == (1280, 704) and t["che_do"] == "nhanh", f"canh {k} sai: {t}")
    tong_ve = round(sum(t["giay_render"] for t in the.values()))
    hai = [x for x in E.KQ["dong_thoi_gian"] if len(x["chay"]) == 2]
    E.kiem(hai, "khong luc nao 2 canh chay cung luc")
    dau = hai[0]["chay"]
    E.kiem(len({v[0] for v in dau.values()}) == 2, f"luc dau 2 GPU khong chia cho 2 du an: {dau}")
    E.ghi("ve xong 4 canh", tong_thoi_gian_thuc=tong_thuc, tong_thoi_gian_ve=tong_ve,
          tang_toc=round(tong_ve / tong_thuc, 2), canh=the, luc_dau_2_gpu=dau)

    t1 = time.time()
    api("POST", f"/api/xuong/{A}/merge")
    api("POST", f"/api/xuong/{B}/merge")
    ok = lambda d: d["merge"]["trang_thai"] is None and d["hang_doi"]["cho_cua_du_an"] == 0 and d["co_video"]
    da_a, da_b = E.cho(A, ok, 600, 3), E.cho(B, ok, 600, 3)
    E.kiem(da_a and da_b and da_a["video_moi"] and da_b["video_moi"], "merge 2 du an loi")
    E.ghi("merge 2 du an", giay=round(time.time() - t1), A=da_a["giay_video"], B=da_b["giay_video"])
    dung.set()
    E.KQ["ket_qua"] = "OK"
    E.ghi("XONG", ram_trong_thap_nhat_gb=E.KQ["ram_trong_thap_nhat_gb"])


if __name__ == "__main__":
    main()
