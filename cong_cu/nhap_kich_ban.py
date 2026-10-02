"""Tach kich ban (docx / txt / chu dan vao) thanh cac CANH co loi doc va (tuy chon) prompt hinh — nut "Nhap kich ban".

  python cong_cu/nhap_kich_ban.py "New Microsoft Word Document.docx"   # in ra cac canh (JSON)

Dang ho tro (mau Word: mau/mau_kich_ban_bang.docx, mau/mau_kich_ban_dong.docx — cong_cu/tao_mau_word.py):
  1. BANG (Word, hoac bang copy tu Word/Excel dan vao -> cot cach nhau bang Tab): hang dau la ten cot —
     "Loi doc" / "Prompt hinh" / "Giay" / "Muc" (co dau, khong dau, hay tieng Anh: Narration, Prompt, Seconds,
     Section deu nhan). Moi hang mot canh. Co bang thi CHI doc bang (chu ngoai bang = huong dan, bo qua).
  2. MOC THOI GIAN: "[00:00 – 00:07] Segment 1On the night ..." (Segment/Scene/Canh/Doan tuy chon, chu co the
     dinh lien so nhu file Word nguoi dung gui 11/09/2026). Loi doc cung dong hoac dong duoi; dong
     "Prompt: ..." (hoac Hinh:/Image:/Visual:) ngay sau la prompt hinh cua canh do.
  3. Khong co moc: moi doan van mot canh; dong "Prompt: ..." gan vao doan truoc no.
  Dong VIET HOA TOAN BO = ten muc (INTRO...). Dong dau tien = ten du an (bo nhan "Ten du an:").
Canh dai qua `toi_da` giay (uoc theo moc, hoac 2,6 tu/giay) tach theo cau; cac phan giu nguyen prompt.
"""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
import zipfile
from pathlib import Path

TU_MOI_GIAY = 2.6          # doc tieng Anh vua phai; Chatterbox do duoc ~2,5-2,8 tu/giay
MOC = re.compile(
    r"^\s*\[\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*[–—-]\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*\]\s*"
    r"(?:(?:segment|scene|cảnh|canh|đoạn|doan)\s*\d+\s*[:.\-–—]?\s*)?(.*)$", re.I)
NHAN_PROMPT = re.compile(r"^\s*(?:prompt(?:\s*h[iì]nh)?|h[iì]nh(?:\s*[aả]nh)?|image|visual)\s*[:：]\s*(.*)$", re.I)
NHAN_LOI = re.compile(r"^\s*(?:l[oờ]i\s*[dđ][oọ]c|narration|voice\s*-?\s*over|vo)\s*[:：]\s*(.*)$", re.I)
NHAN_TEN = re.compile(r"^\s*(?:t[eê]n\s*d[uự]\s*[aá]n|title|project)\s*[:：]\s*", re.I)


def bo_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s or ""))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").replace("đ", "d").replace("Đ", "D").lower()


def _chu_doan(p: str) -> str:
    p = re.sub(r"<w:(tab|br)[^>]*/>", "<w:t> </w:t>", p)        # tab/xuong dong mem = khoang trang
    return html.unescape("".join(re.findall(r"<w:t(?: [^>]*)?>(.*?)</w:t>", p, re.S)))


def doc_tep(duong: Path | None = None, chu: str | None = None) -> dict:
    """{"doan": [dong ngoai bang], "bang": [[[o, ...], ...], ...]} tu .docx, .txt/.md hoac chu dan vao."""
    doan, bang = [], []
    if chu is None and duong.suffix.lower() == ".docx":
        xml = zipfile.ZipFile(duong).read("word/document.xml").decode("utf-8")
        for manh in re.split(r"(<w:tbl>.*?</w:tbl>)", xml, flags=re.S):
            if manh.startswith("<w:tbl>"):
                hang = []
                for tr in re.findall(r"<w:tr[ >].*?</w:tr>", manh, re.S):
                    hang.append([" ".join(_chu_doan(p) for p in re.findall(r"<w:p[ >].*?</w:p>", tc, re.S)).strip()
                                 for tc in re.findall(r"<w:tc[ >].*?</w:tc>", tr, re.S)])
                bang.append(hang)
            else:
                doan += [_chu_doan(p) for p in re.findall(r"<w:p[ >].*?</w:p>", manh, re.S)]
    else:
        if chu is None:
            chu = duong.read_text(encoding="utf-8", errors="replace")
        dong = chu.replace("\r", "").split("\n")
        # bang copy tu Word/Excel: cac o cach nhau bang Tab
        tsv = [d.split("\t") for d in dong if "\t" in d]
        if tsv and _cot(tsv[0]):
            bang.append(tsv)
            doan = [d for d in dong if "\t" not in d]
        else:
            doan = dong
    return {"doan": [re.sub(r"\s+", " ", d).strip() for d in doan], "bang": bang}


def doc_doan(duong: Path | None = None, chu: str | None = None) -> list[str]:
    """Giu cho cho cu: chi cac dong ngoai bang."""
    return doc_tep(duong, chu)["doan"]


def _cot(dau: list[str]) -> dict:
    """Ten cot -> vi tri. Can it nhat cot loi doc hoac prompt."""
    cot = {}
    for i, t in enumerate(dau):
        t = bo_dau(t)
        if "prompt" in t or re.search(r"\b(hinh|image|visual)\b", t):
            cot.setdefault("prompt", i)
        elif re.search(r"\b(loi|narration|voice|script|kich ban|noi dung)\b", t):
            cot.setdefault("loi", i)
        elif re.search(r"\b(giay|second|seconds|sec|thoi luong|duration)\b", t):
            cot.setdefault("giay", i)
        elif re.search(r"\b(muc|section|phan|chuong|part)\b", t):
            cot.setdefault("muc", i)
    return cot if ("loi" in cot or "prompt" in cot) else {}


def _giay(h: str, m: str, s: str | None) -> int:
    return int(h) * 3600 + int(m) * 60 + int(s) if s is not None else int(h) * 60 + int(m)


def _la_muc(d: str) -> bool:
    chu = re.sub(r"[^A-Za-zÀ-ỹ]", "", d)
    return 2 <= len(d) <= 80 and len(chu) >= 3 and chu == chu.upper()


def _cau(chu: str) -> list[str]:
    return [c.strip() for c in re.split(r"(?<=[.!?…])\s+(?=[\"“'A-ZÀ-Ỹ0-9])", chu) if c.strip()]


def _tach_dai(chu: str, giay: float, toi_da: float) -> list[tuple[str, float]]:
    """Tach mot doan dai thanh cac phan <= toi_da giay, cat o ranh gioi cau, chia giay theo so tu."""
    if giay <= toi_da:
        return [(chu, round(giay, 1))]
    cau, tu_giay = _cau(chu), giay / max(1, len(chu.split()))
    phan, dang = [], []
    for c in cau:
        if dang and (len(" ".join(dang + [c]).split()) * tu_giay) > toi_da:
            phan.append(" ".join(dang))
            dang = []
        dang.append(c)
    if dang:
        phan.append(" ".join(dang))
    return [(p, round(len(p.split()) * tu_giay, 1)) for p in phan]


def _canh(loi: str, prompt: str, giay: float, muc: str, moc: str, toi_da: float) -> list[dict]:
    loi, prompt = loi.strip(), prompt.strip()
    if not loi:
        return [{"loi_doc": "", "prompt": prompt, "giay_du_kien": round(giay, 1), "muc": muc, "moc": moc}]
    return [{"loi_doc": p, "prompt": prompt, "giay_du_kien": g, "muc": muc, "moc": moc}
            for p, g in _tach_dai(loi, giay, toi_da)]


def _tach_bang(bang: list[list[list[str]]], toi_da: float) -> list[dict]:
    canh = []
    for hang in bang:
        dau = next((i for i, h in enumerate(hang) if _cot(h)), None)
        if dau is None:
            continue
        cot, muc = _cot(hang[dau]), ""
        lay = lambda h, k: (h[cot[k]] if k in cot and cot[k] < len(h) else "").strip()
        for h in hang[dau + 1:]:
            loi, prompt = lay(h, "loi"), lay(h, "prompt")
            muc = lay(h, "muc") or muc
            if not loi and not prompt:
                continue
            so = re.search(r"\d+(?:[.,]\d+)?", lay(h, "giay"))
            giay = float(so.group().replace(",", ".")) if so else (len(loi.split()) / TU_MOI_GIAY if loi else 5.0)
            canh += _canh(loi, prompt, max(1.0, giay), muc, "", toi_da)
    return canh


def tach(tep: dict | list[str], toi_da: float = 19.5) -> dict:
    tep = tep if isinstance(tep, dict) else {"doan": tep, "bang": []}
    doan = tep["doan"]
    ten = next((NHAN_TEN.sub("", d) for d in doan if d), "")
    if any(_cot(h) for b in tep["bang"] for h in b):
        return {"ten": ten[:100], "canh": _tach_bang(tep["bang"], toi_da)}

    co_moc = any(MOC.match(d) for d in doan if d)
    tho, muc, ten_da_lay = [], "", False      # tho: canh chua tach {loi, prompt, giay, muc, moc, pha}
    for d in doan:
        if not d:
            continue
        if not ten_da_lay:
            ten_da_lay = True
            if not MOC.match(d) and not NHAN_PROMPT.match(d):
                continue                       # dong dau = ten du an
        m = MOC.match(d) if co_moc else None
        mp = NHAN_PROMPT.match(d)
        ml = NHAN_LOI.match(d)
        if m:
            bd, kt = _giay(m.group(1), m.group(2), m.group(3)), _giay(m.group(4), m.group(5), m.group(6))
            tho.append({"loi": m.group(7).strip(), "prompt": "", "giay": max(1.0, kt - bd), "muc": muc,
                        "moc": f"{m.group(1)}:{m.group(2)}", "pha": "loi"})
        elif mp:
            if tho:
                tho[-1]["prompt"] = (tho[-1]["prompt"] + " " + mp.group(1)).strip()
                tho[-1]["pha"] = "prompt"
        elif ml and tho and not co_moc is False:
            tho[-1]["loi"] = (tho[-1]["loi"] + " " + ml.group(1)).strip()
        elif _la_muc(d):
            muc = d
        elif co_moc:
            if not tho:
                continue                       # huong dan truoc moc dau tien
            k = "prompt" if tho[-1]["pha"] == "prompt" else "loi"
            tho[-1][k] = (tho[-1][k] + " " + d).strip()
        else:                                  # khong co moc: moi doan van mot canh
            loi = ml.group(1) if ml else d
            tho.append({"loi": loi, "prompt": "", "giay": len(loi.split()) / TU_MOI_GIAY, "muc": muc, "moc": "", "pha": "loi"})
    canh = []
    for t in tho:
        if t["loi"] or t["prompt"]:
            g = t["giay"] if t["moc"] or not t["loi"] else len(t["loi"].split()) / TU_MOI_GIAY
            canh += _canh(t["loi"], t["prompt"], g, t["muc"], t["moc"], toi_da)
    return {"ten": ten[:100], "canh": canh}


def main() -> None:
    kq = tach(doc_tep(Path(sys.argv[1])), float(sys.argv[2]) if len(sys.argv) > 2 else 19.5)
    print(json.dumps(kq, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
