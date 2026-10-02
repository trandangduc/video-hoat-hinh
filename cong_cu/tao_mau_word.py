"""Tao file Word (.docx) cho Xuong video: FILE MAU kich ban va XUAT du an ra Word — khong can python-docx.

  python cong_cu/tao_mau_word.py            # -> mau/mau_kich_ban_bang.docx + mau/mau_kich_ban_dong.docx

.docx chi la zip vai file XML nen dung tay duoc. Nguoi dung viet LOI DOC + PROMPT HINH cho tung canh trong Word
(bang: moi hang mot canh), nhap vao Xuong -> may lay dung prompt do, khong goi Gemma (cong_cu/nhap_kich_ban.py).
"""
from __future__ import annotations

import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

GOC = Path(__file__).resolve().parent.parent
MAU = GOC / "mau"
NS = ('xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
      'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"')
COT = [("STT", 600), ("Mục", 1700), ("Lời đọc (tiếng Anh)", 5800), ("Prompt hình (tiếng Anh)", 6200), ("Giây", 1000)]


def _chu(s: str, dam: bool = False, nghieng: bool = False, co: int | None = None, mau: str | None = None) -> str:
    rpr = ("<w:b/>" if dam else "") + ("<w:i/>" if nghieng else "") + \
          (f'<w:sz w:val="{co}"/><w:szCs w:val="{co}"/>' if co else "") + (f'<w:color w:val="{mau}"/>' if mau else "")
    dong = str(s).split("\n")
    noi = '<w:br/>'.join(f'<w:t xml:space="preserve">{escape(d)}</w:t>' for d in dong)
    return f"<w:r>{'<w:rPr>' + rpr + '</w:rPr>' if rpr else ''}{noi}</w:r>"


def _doan(s: str = "", sau: int = 120, **k) -> str:
    return f'<w:p><w:pPr><w:spacing w:after="{sau}"/></w:pPr>{_chu(s, **k) if s else ""}</w:p>'


def _o(s: str, rong: int, dau: bool = False) -> str:
    to = '<w:shd w:val="clear" w:color="auto" w:fill="F3E3D3"/>' if dau else ""
    return (f'<w:tc><w:tcPr><w:tcW w:w="{rong}" w:type="dxa"/>{to}</w:tcPr>'
            f'<w:p><w:pPr><w:spacing w:after="0"/></w:pPr>{_chu(s, dam=dau) if s else ""}</w:p></w:tc>')


def _bang(hang: list[list[str]]) -> str:
    vien = "".join(f'<w:{b} w:val="single" w:sz="4" w:space="0" w:color="BFBFBF"/>'
                   for b in ("top", "left", "bottom", "right", "insideH", "insideV"))
    pr = (f'<w:tblPr><w:tblW w:w="{sum(r for _, r in COT)}" w:type="dxa"/><w:tblBorders>{vien}</w:tblBorders>'
          '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="60" w:type="dxa"/><w:left w:w="90" w:type="dxa"/>'
          '<w:bottom w:w="60" w:type="dxa"/><w:right w:w="90" w:type="dxa"/></w:tblCellMar></w:tblPr>')
    luoi = "<w:tblGrid>" + "".join(f'<w:gridCol w:w="{r}"/>' for _, r in COT) + "</w:tblGrid>"
    dau = '<w:tr><w:trPr><w:tblHeader/></w:trPr>' + "".join(_o(t, r, True) for t, r in COT) + "</w:tr>"
    than = "".join("<w:tr>" + "".join(_o(o, r) for o, (_, r) in zip(h, COT)) + "</w:tr>" for h in hang)
    return f"<w:tbl>{pr}{luoi}{dau}{than}</w:tbl>"


def _goi(than: str, ra: Path) -> Path:
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {NS}><w:body>{than}'
           '<w:sectPr><w:pgSz w:w="16838" w:h="11906" w:orient="landscape"/>'
           '<w:pgMar w:top="720" w:right="720" w:bottom="720" w:left="720" w:header="360" w:footer="360" w:gutter="0"/>'
           '</w:sectPr></w:body></w:document>')
    kieu = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Styles xmlns="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'.replace("Styles", "w:styles").replace('xmlns=', 'xmlns:w=')
            + '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Arial" w:hAnsi="Arial" w:cs="Arial" w:eastAsia="Arial"/>'
            '<w:sz w:val="21"/><w:szCs w:val="21"/><w:lang w:val="vi-VN"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style></w:styles>')
    loai = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
            '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
            '</Types>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
            '</Relationships>')
    drels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
             '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
             '</Relationships>')
    ra.parent.mkdir(parents=True, exist_ok=True)
    tam = ra.with_suffix(".tmp")
    with zipfile.ZipFile(tam, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", loai)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/_rels/document.xml.rels", drels)
        z.writestr("word/styles.xml", kieu)
    tam.replace(ra)
    return ra


HUONG_DAN_BANG = [
    "Mỗi HÀNG trong bảng là một cảnh. Xưởng chỉ đọc BẢNG — chữ ngoài bảng (như các dòng hướng dẫn này) được bỏ qua, "
    "trừ dòng đầu tiên là tên dự án.",
    "• Lời đọc: tiếng Anh, máy đọc thành giọng; cảnh tự dài theo giọng. Để trống nếu cảnh không có lời (khi đó điền cột Giây).",
    "• Prompt hình: tả thứ máy quay THẤY — người/vật/nơi chốn, ánh sáng, và một chuyển động máy (slow push-in, slow pan…). "
    "Để trống thì máy tự viết từ lời đọc (nếu bật ô 'Cảnh thiếu prompt thì máy tự viết' lúc nhập). "
    "Không ghi phong cách ở đây — phong cách đặt một lần trong dự án.",
    "• Giây: chỉ cần cho cảnh không có lời đọc. • Mục: tuỳ chọn (INTRO, THE EXPEDITION…); hàng để trống Mục lấy Mục của hàng trên.",
    "Thêm hàng: đặt con trỏ ở ô cuối cùng của bảng rồi bấm Tab. Có thể xoá cột STT, đổi thứ tự cột — Xưởng nhận cột theo TÊN.",
]
VI_DU = [
    ["1", "INTRO", "On the night of February 1st, 1959, nine experienced hikers did something that, to this day, no one can fully explain.",
     "An old photograph pinned among torn notebook pages showing nine hikers in heavy winter jackets inside a canvas tent on a snowy slope, visible breath in the cold air, slow push-in", ""],
    ["2", "", "They cut open their own tent — from the inside — and fled into the freezing night, with temperatures dropping to minus thirty degrees.",
     "An old photograph pinned among torn notebook pages showing a canvas tent with a long jagged slash in its side, snow blowing through the tear, slow push-in", ""],
    ["3", "", "No shoes. No coats. Some were wearing only socks. One was even completely barefoot.", "", ""],
    ["4", "THE EXPEDITION", "",
     "A hand-drawn map of the northern Ural mountains on aged paper with a dotted route leading to a lone mountain peak, slow pan", "4"],
    ["5", "", "In the winter of 1959, a group of nine students set out from the city of Sverdlovsk on an ambitious trekking expedition.",
     "A vintage photograph of nine young students with large backpacks standing on a snowy railway platform, smiling, slow drift", ""],
    ["6", "ENDING", "Thank you for watching and following The Lost Archive. I'll see you again in the next story.",
     "A pencil sketch of a lone mountain peak under a starry sky on aged paper, slow push-in", ""],
]


def tao_docx_bang(ten: str, hang: list[list[str]], ra: Path, huong_dan: list[str] | None = None) -> Path:
    than = _doan(f"Tên dự án: {ten}", 160, dam=True, co=32)
    for h in (huong_dan if huong_dan is not None else HUONG_DAN_BANG):
        than += _doan(h, 60, co=19, mau="555555")
    than += _doan("", 60) + _bang(hang)
    return _goi(than, ra)


def tao_mau_dong(ra: Path) -> Path:
    than = _doan("Tên dự án: THE DYATLOV PASS MYSTERY", 160, dam=True, co=32)
    for h in ["Kiểu dòng: mỗi mốc giờ [mm:ss – mm:ss] là một cảnh. Lời đọc viết ngay sau mốc (cùng dòng hoặc dòng dưới). "
              "Dòng bắt đầu bằng chữ Prompt và dấu hai chấm là prompt hình của cảnh đó; bỏ dòng này thì máy tự viết.",
              "Dòng VIẾT HOA TOÀN BỘ là tên mục. Viết hướng dẫn/ghi chú TRƯỚC mốc giờ đầu tiên — sau đó mọi dòng thường được coi là lời đọc hoặc prompt."]:
        than += _doan(h, 60, co=19, mau="555555")
    dong = [("INTRO", True),
            ("[00:00 – 00:07] Segment 1", False), (VI_DU[0][2], False), ("Prompt: " + VI_DU[0][3], False),
            ("[00:07 – 00:15] Segment 2", False), (VI_DU[1][2], False), ("Prompt: " + VI_DU[1][3], False),
            ("[00:15 – 00:22] Segment 3 " + VI_DU[2][2], False),
            ("THE EXPEDITION", True),
            ("[00:22 – 00:32] Segment 4 " + VI_DU[4][2], False), ("Prompt: " + VI_DU[4][3], False),
            ("ENDING", True),
            ("[00:32 – 00:39] Segment 5", False), (VI_DU[5][2], False), ("Prompt: " + VI_DU[5][3], False)]
    for s, muc in dong:
        than += _doan(s, 60, dam=muc)
    return _goi(than, ra)


def xuat_du_an(da: dict, ra: Path) -> Path:
    """Du an dang co -> Word dang bang (sua prompt trong Word roi nhap lai voi 'Thay toan bo canh')."""
    hang, muc_truoc = [], None
    for i, c in enumerate(da.get("canh") or []):
        muc = c.get("muc") or ""
        hang.append([str(i + 1), muc if muc != muc_truoc else "", c.get("loi_doc") or "", c.get("prompt") or "",
                     "" if (c.get("loi_doc") or "").strip() else f"{c.get('giay') or ''}"])
        muc_truoc = muc
    return tao_docx_bang(da.get("ten") or "Dự án", hang, ra, HUONG_DAN_BANG)


def main() -> None:
    a = tao_docx_bang("THE DYATLOV PASS MYSTERY", VI_DU, MAU / "mau_kich_ban_bang.docx")
    b = tao_mau_dong(MAU / "mau_kich_ban_dong.docx")
    print(a, b, sep="\n")


if __name__ == "__main__":
    sys.exit(main())
