"""Len kich ban video tu mot cau chuyen viet bang loi thuong — kieu ChatGPT, nhung chay TAI MAY.

Dung Gemma-4 E2B (models/text_encoders/gemma4_e2b_it_int8_convrot.safetensors) qua node
TextGenerate cua ComfyUI. Da do ngay 10/09/2026:
  - Gemma-4 12B "with-proj" cua LTX KHONG sinh chu duoc: ra toan "SSSS...", ca chu lan anh.
  - Gemma-4 E2B: len kich ban 10 giay mat ~30s va ra JSON hop le; doc anh mau ~15s, ta dung.

Model nho nen hay pham luat — do duoc: tong giay 11.1 thay vi 10, chu chen tieng Anh du
cau chuyen tieng Viet, prompt tru tuong ("a visual representation of energy"), tu y them
"film grain" (chinh chu nay lam LTX ve ra dai phim den). Nen code DON LAI sau khi doc JSON
chu khong tin model.

  python cong_cu/len_kich_ban.py "Ke ve Marie Curie..." --giay 10 --nhip nhanh [--anh anh.png]
"""
from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

GOC = Path(__file__).resolve().parent.parent
MAY = "http://127.0.0.1:8188"
MODEL = "gemma4_e2b_it_int8_convrot.safetensors"

# (giay ngan nhat, dai nhat, trung binh) cua mot canh
NHIP = {"nhanh": (0.6, 1.8, 1.1), "vua": (2.0, 4.0, 3.0), "cham": (4.0, 7.0, 5.0)}
KIEU_CHU = ("nhan", "viet", "o_chu", "tieu_de")
# Phong cach dung san — dung chung cho giao dien (qua /api/phong-cach) va de model CHON khi nguoi
# dung de "tu chon". Cho model tu nghi thi ra nhat nheo va nguy hiem: do duoc "Dark, dramatic,
# historical" -> ca video toi den, canh 3 gan nhu man hinh den. Nen bat no chon trong danh sach.
PHONG_CACH_MAU = [
    ("collage", "Collage cổ điển", "vintage sepia and black-and-white collage, torn paper edges, handwritten notes, old scientific illustrations"),
    ("dien_anh", "Ảnh thật điện ảnh", "cinematic photorealistic footage, natural light, shallow depth of field, rich colour grading"),
    ("vector", "Vector phẳng", "flat vector cartoon animation, clean bold black outlines, characters with simple rounded heads and visible eyes and mouth, flat saturated colours, simple uncluttered background"),
    ("ve_tay", "Tài liệu vẽ tay", "hand-drawn documentary animation in thick black marker on plain cream paper, bold confident strokes, human figures with clear head, torso, arms and legs, sparse background"),
    ("anime", "Anime", "soft anime cel animation, clean thin ink lines, expressive eyes and clear facial features, two-tone cel shading, muted pastel palette"),
    ("son_dau", "Tranh sơn dầu", "painterly oil-on-canvas animation, thick visible brush strokes, figures with readable silhouettes and defined faces, rich saturated colour, dramatic side lighting"),
]
PHONG_CACH_MAC_DINH = PHONG_CACH_MAU[0][2]
# Prompt con chu toi thi LTX ve dung la TOI: do duoc 4/5 canh gan nhu den.
TOI_CHU = re.compile(r"\b(dim(ly)?([- ]lit)?|dark(ness|ened)?|shadow(y|s)?|pitch[- ]black|black background|"
                     r"silhouettes?|murky|gloomy|night)\b", re.I)

# Cum tu lam LTX ve ra rac: "film grain" -> dai phim den, "text/letters" -> chu meo,
# "representation/montage/symbolic" -> hinh vo dinh.
CAM = re.compile(
    r"\b(film[- ]?grain|grainy|grain|film strips?|sprocket holes?|borders?|on-screen text|text|letters?|"
    r"words?|captions?|typography|a visual representation of|a representation of|"
    r"a montage of|montage|a symbolic shot of|symbolic)\b", re.I)
VIET = re.compile(r"[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", re.I)


# ------------------------------------------------------------------ goi ComfyUI

def _goi(duong: str, data: dict | None = None, may: str | None = None) -> dict:
    req = urllib.request.Request((may or MAY) + duong, data=json.dumps(data).encode() if data else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def comfy_ranh() -> str:
    """ComfyUI (GPU0 :8188 / GPU1 :8189) co hang cho ngan nhat — viet chu khong phai doi luot ve dai o GPU kia."""
    tot, chon = None, MAY
    for cong in (8188, 8189):
        u = f"http://127.0.0.1:{cong}"
        try:
            q = _goi("/queue", may=u)
        except Exception:
            continue
        n = len(q.get("queue_running", [])) + len(q.get("queue_pending", []))
        if tot is None or n < tot:
            tot, chon = n, u
    return chon


def _turn(he_thong: str, nguoi_dung: str, co_anh: bool = False) -> str:
    """Tu dinh dang luot Gemma-4. Prompt bat dau bang <|turn> thi tokenizer tu bo template."""
    anh = "<|image><|image|><image|>\n\n" if co_anh else ""
    return (f"<|turn>system\n{he_thong}<turn|>\n<|turn>user\n{anh}{nguoi_dung}<turn|>\n"
            f"<|turn>model\n<|channel>final\n")


def sinh_chu(prompt: str, max_len: int, anh_comfy: str | None = None, cho_toi_da: int = 1800,
             may: str | None = None) -> str:
    wf = {"1": {"class_type": "CLIPLoader", "inputs": {"clip_name": MODEL, "type": "ltxv", "device": "default"}},
          "2": {"class_type": "TextGenerate", "inputs": {"clip": ["1", 0], "prompt": prompt, "max_length": max_len,
                "sampling_mode": "off", "thinking": False, "use_default_template": False}},
          "3": {"class_type": "PreviewAny", "inputs": {"source": ["2", 0]}}}
    if anh_comfy:
        wf["4"] = {"class_type": "LoadImage", "inputs": {"image": anh_comfy}}
        wf["5"] = {"class_type": "ImageScale", "inputs": {"image": ["4", 0], "upscale_method": "lanczos",
                   "width": 768, "height": 768, "crop": "disabled"}}
        wf["2"]["inputs"]["image"] = ["5", 0]
    try:
        # front=True: chen len DAU hang doi — dang render video khac thi chi phai cho het canh dang chay
        pid = _goi("/prompt", {"prompt": wf, "client_id": uuid.uuid4().hex, "front": True}, may)["prompt_id"]
    except urllib.error.URLError as e:
        raise RuntimeError(f"Khong goi duoc ComfyUI ({e}). Bat bang: bash cong_cu/comfy.sh len") from e
    t0 = time.time()
    while time.time() - t0 < cho_toi_da:
        time.sleep(1.5)
        h = _goi(f"/history/{pid}", may=may).get(pid)
        if not h:
            continue
        tt = h.get("status", {})
        if tt.get("status_str") == "error":
            loi = [m for m in tt.get("messages", []) if m[0] == "execution_error"]
            raise RuntimeError("ComfyUI bao loi: " + json.dumps(loi, ensure_ascii=False)[:600])
        if tt.get("completed"):
            txt = h["outputs"].get("3", {}).get("text", [""])
            return (txt[0] if isinstance(txt, list) else str(txt)).strip()
    raise RuntimeError("Qua lau khong xong (ComfyUI dang ban?)")


# ------------------------------------------------------- prompt hinh tu loi doc

def viet_prompt_canh(loi_doc: str, phong_cach: str = "", truoc: str = "", sau: str = "", nhan_vat: str = "") -> str:
    """Loi doc cua MOT canh -> mot prompt hinh tieng Anh (Xuong: nguoi dung de trong o Prompt hinh).

    Nguoi dung hay dan cau PHONG CACH vao o prompt ("vintage sepia collage, film grain, rapid montage") -> LTX
    ve nen giay mo khong chu the. Prompt phai ta thu may quay THAY; phong cach Xuong tu ghep vao truoc.
    Loi doc canh truoc/sau giup canh noi mach nhau."""
    collage = "collage" in (phong_cach or "").lower()
    cach = ('Write it as ONE element of a vintage collage, choosing among: "an old photograph pinned among torn notebook '
            'pages showing ...", "a pencil sketch of ... on aged paper", "a hand-drawn map of ...", "a scientific '
            'illustration of ...", "a vintage desk still life with ...". ' if collage else "")
    nv = (f'The main character looks like this: {nhan_vat}. When the scene is about them, call them "the character". '
          if nhan_vat else "")
    he_thong = (
        "You write ONE English prompt for a text-to-video model, for one scene of a narrated documentary video. "
        "Describe only what the camera SEES: a physical, visible subject (people, objects or a place) large and centred "
        "in frame, its setting and light, then end with one slow camera move (slow push-in, slow pan or slow drift). "
        f"{cach}"
        "When the narration names concrete things, show them literally. When it is abstract (a question, a theory, "
        "a greeting, a conclusion), show one fitting concrete image instead. "
        "Never ask for text, letters, captions, signs, logos, film grain, borders, montage, split screen or symbols. "
        "Keep the scene bright and clearly visible. Do not describe the art style. "
        f"{nv}At most 45 words. Output only the prompt.")
    nguoi = (f"Previous scene narration: {truoc or '(none)'}\n"
             f"THIS scene narration: {loi_doc}\n"
             f"Next scene narration: {sau or '(none)'}")
    txt = sinh_chu(_turn(he_thong, nguoi), 140, may=comfy_ranh())
    txt = re.sub(r"<think>.*?(?:</think>|$)", "", txt, flags=re.S).strip().strip('"')
    p = _sach_prompt(txt.split("\n")[0])
    p = re.sub(r"\.\s+(?=(?:a\s+)?slow\b)", ", ", p)          # "...backdrop. slow push-in" -> ", slow push-in"
    if len(p) < 12:
        raise RuntimeError(f"Gemma khong viet duoc prompt cho canh: {txt[:120]!r}")
    if TOI_CHU.search(p) and "clearly lit" not in p:
        p += ", clearly lit and visible"
    return p


# ----------------------------------------------------------------- doc anh mau

def mo_ta_anh(duong_anh: Path) -> str:
    """Anh mau -> mot cau tieng Anh ta nhan vat, de ghep vao prompt cac canh co nhan vat."""
    ten = f"mau_{uuid.uuid4().hex[:8]}{duong_anh.suffix.lower() or '.png'}"
    dich = GOC / "ComfyUI" / "input" / ten
    shutil.copy(duong_anh, dich)
    try:
        txt = sinh_chu(_turn(
            "You describe images precisely for a text-to-video model.",
            # Ban cu (35 tu, style de cuoi) ra "cartoon-style ... straw hat": LTX ve thanh nhan vat 3D doi mu
            # rom vanh tron trong khi anh la 2D net den day doi non la. Style va hinh dang do vat phai CU THE.
            "Describe ONLY the main character (the person or creature) in ONE English sentence of at most 50 words, "
            "ignoring the background and the objects around them. "
            "Start with the exact art style (for example flat 2D cartoon with thick black outlines, 3D animated render, "
            "anime, watercolour, or photograph). Then the body proportions, the face, the exact shape of any hair or "
            "headwear, and the clothing with colours and patterns. Name distinctive items precisely. "
            "No commentary.", co_anh=True), 160, anh_comfy=ten)
    finally:
        dich.unlink(missing_ok=True)
    txt = re.sub(r"<think>.*?(?:</think>|$)", "", txt, flags=re.S).strip().strip('"')
    # Model hay lap nguyen cau ma KHONG xuong dong (do duoc: "...expression.A cartoon-style ...
    # expression.") nen cat theo dong la chua du — lay dung CAU dau tien.
    dong = txt.split("\n")[0].strip()
    return re.split(r"(?<=[.!?])\s*(?=[A-Z])", dong, maxsplit=1)[0].strip()


# ----------------------------------------------------------------- len kich ban

def ngon_ngu(chu: str) -> str:
    return "Vietnamese" if VIET.search(chu) else "English"


def _he_thong(giay: float, nhip: str, nn: str, nhan_vat: str, phong_cach: str) -> str:
    lo, hi, tb = NHIP[nhip]
    so = max(2, round(giay / tb))
    ghi_nv = (f"\n- The main character looks like this: {nhan_vat}. Set \"co_nhan_vat\": true on scenes where "
              f"this character appears and refer to them simply as \"the character\" in the prompt."
              if nhan_vat else "\n- Set \"co_nhan_vat\": false on every scene.")
    if phong_cach == PHONG_CACH_MAC_DINH:
        # Cong thuc da ra video_collage.mp4: moi canh la MOT manh collage (anh cu ghim giua trang so
        # xe, phac thao but chi, ban do ve tay...), chu the to o giua, may quay day/lia cham. Chi ghi
        # chu "collage" o phong cach ma prompt ta canh tran thi LTX ve canh thuong nhuom sepia.
        cach_viet = ('Write each prompt as ONE element of a vintage collage, choosing among: "an old photograph pinned '
                     'among torn notebook pages showing ...", "a pencil sketch of ... on aged paper", "a hand-drawn map '
                     'of ...", "an anatomical or scientific illustration of ...", "a vintage desk still life with ...". '
                     'Vary the element from scene to scene. The subject must be large and clearly visible in the centre. '
                     'End with one slow camera move: slow push-in, slow pan or slow drift.')
        vi_du = ("An old photograph pinned among torn notebook pages showing six hikers in heavy winter jackets "
                 "walking through deep snow, slow push-in")
    else:
        cach_viet = ("It must name a physical, visible subject (a person, an object or a place) large in frame, "
                     "its setting, and a slow camera move.")
        vi_du = "An old wooden warehouse full of iron barrels lit by a hanging lamp, slow push-in"
    return f"""You are the director of a short video. Plan it from the user's story.
Return ONLY valid JSON, no markdown, no commentary, using exactly this schema:
{{"tieu_de": string, "canh": [{{"prompt": string, "giay": number, "co_nhan_vat": boolean}}]}}
Rules:
- The whole video lasts {giay:g} seconds. Make about {so} scenes, each {lo:g} to {hi:g} seconds.
- "prompt": ONE English sentence for a text-to-video model. {cach_viet} Never describe abstract ideas, energy, symbols or montages. Never ask for text, letters, film grain or borders. Every scene must be clearly visible and well lit: avoid pitch-dark scenes, black backgrounds, silhouettes and fog; if the story happens in the dark, show a lamp or a glow lighting the subject.{ghi_nv}
- "tieu_de": a short title in {nn}.
Example scene: {{"prompt": "{vi_du}", "giay": 1.2, "co_nhan_vat": false}}"""


def _doc_json(txt: str) -> dict:
    s = re.sub(r"<think>.*?(?:</think>|$)", "", txt, flags=re.S)
    s = re.sub(r"```(?:json)?", "", s)
    a, b = s.find("{"), s.rfind("}")
    if a < 0 or b <= a:
        raise ValueError("khong co JSON")
    s = s[a:b + 1]
    s = re.sub(r",\s*([}\]])", r"\1", s)          # dau phay thua truoc } hoac ]
    return json.loads(s)


def _sach_prompt(p: str) -> str:
    p = CAM.sub("", str(p))
    p = re.sub(r"\s+,", ",", re.sub(r"\s{2,}", " ", p))
    p = re.sub(r"(,\s*){2,}", ", ", p).strip(" ,.;")
    return p[:1].upper() + p[1:] if p else p


def lam_sach(d: dict, giay: float, nhip: str, phong_cach: str, nhan_vat: str) -> dict:
    lo, hi, tb = NHIP[nhip]
    canh = []
    for c in d.get("canh") or []:
        if not isinstance(c, dict):
            continue
        p = _sach_prompt(c.get("prompt", ""))
        if len(p) < 12:
            continue
        if TOI_CHU.search(p) and "clearly lit" not in p:
            p += ", clearly lit and visible"
        try:
            g = float(c.get("giay", tb))
        except (TypeError, ValueError):
            g = tb
        chu = []
        for k in (c.get("chu") or [])[:2]:
            if not isinstance(k, dict):
                continue
            nd = re.sub(r"\s+", " ", str(k.get("noi_dung", ""))).strip().strip('"')
            if not nd:
                continue
            nd = " ".join(nd.split(" ")[:8])[:60]
            kieu = k.get("kieu") if k.get("kieu") in KIEU_CHU else "nhan"
            if kieu == "o_chu":
                if " " in nd or len(nd) > 12:
                    kieu = "tieu_de"
                else:
                    nd = nd.upper()
            chu.append({"noi_dung": nd, "kieu": kieu})
        canh.append({"prompt": p, "giay": min(hi, max(lo, g)),
                     "co_nhan_vat": bool(c.get("co_nhan_vat")) and bool(nhan_vat), "chu": chu})
    if len(canh) < 2:
        raise ValueError(f"model chi ra {len(canh)} canh dung duoc")
    canh = canh[:max(2, math.floor(giay / lo))]

    # Khong chen chu len hinh: nguoi dung muon video nhu video_collage.mp4 nhung KHONG co chu
    # (yeu cau 10/09/2026). Giu truong "chu" rong de may dung video van doc duoc.
    for c in canh:
        c["chu"] = []

    # Ep tong dung so giay: co gian deu, lam tron 0.05, phan du don vao canh dai nhat
    he = giay / sum(c["giay"] for c in canh)
    for c in canh:
        c["giay"] = round(round(c["giay"] * he / 0.05) * 0.05, 2)
    du = round(giay - sum(c["giay"] for c in canh), 2)
    dai = max(canh, key=lambda c: c["giay"])
    dai["giay"] = round(dai["giay"] + du, 2)

    pc = phong_cach.strip()
    if not pc:
        tra = re.sub(r"[\s-]+", "_", str(d.get("phong_cach", "")).lower())
        pc = next((m for k, _, m in PHONG_CACH_MAU if re.search(rf"\b{k}\b", tra)), PHONG_CACH_MAC_DINH)
    return {"tieu_de": str(d.get("tieu_de") or "Video").strip()[:80], "phong_cach": pc, "canh": canh}


def len_kich_ban(cau_chuyen: str, giay: float = 10, nhip: str = "nhanh",
                 nhan_vat: str = "", phong_cach: str = "", bien_the: int = 0) -> dict:
    """bien_the > 0: xin mot ban KHAC. Model chay greedy (sampling off) nen hoi lai y nguyen se
    ra y nguyen — them mot dong nhac khac di de doi cau tra loi."""
    # Mac dinh LUON la collage (cong thuc cua video_collage.mp4) — khong de model tu chon.
    phong_cach = (phong_cach or "").strip() or PHONG_CACH_MAC_DINH
    nn = ngon_ngu(cau_chuyen)
    lo, hi, tb = NHIP[nhip]
    so_max = max(2, math.floor(giay / lo))
    he = _he_thong(giay, nhip, nn, nhan_vat, phong_cach)
    max_len = min(8000, 300 + 120 * so_max)
    goc = cau_chuyen + (f"\n\n(Alternative version {bien_the}: choose different shots, angles and captions "
                        f"than an obvious retelling.)" if bien_the else "")
    loi = None
    for lan in range(2):
        nguoi = goc if lan == 0 else (
            goc + "\n\n(Your previous answer was not valid JSON. Answer with the JSON object only.)")
        txt = sinh_chu(_turn(he, nguoi), max_len)
        try:
            kq = lam_sach(_doc_json(txt), giay, nhip, phong_cach, nhan_vat)
            kq.update(ngon_ngu=nn, nhan_vat=nhan_vat)
            return kq
        except (ValueError, json.JSONDecodeError) as e:
            loi = f"{e} | model tra: {txt[:300]}"
    raise RuntimeError(f"Khong len duoc kich ban sau 2 lan: {loi}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cau_chuyen")
    ap.add_argument("--giay", type=float, default=10)
    ap.add_argument("--nhip", choices=list(NHIP), default="nhanh")
    ap.add_argument("--anh", help="anh mau nhan vat")
    ap.add_argument("--phong-cach", default="")
    a = ap.parse_args()
    t0 = time.time()
    nv = ""
    if a.anh:
        nv = mo_ta_anh(Path(a.anh))
        print(f"# nhan vat ({time.time() - t0:.1f}s): {nv}", file=sys.stderr)
    kq = len_kich_ban(a.cau_chuyen, a.giay, a.nhip, nv, a.phong_cach)
    print(json.dumps(kq, ensure_ascii=False, indent=2))
    print(f"# xong sau {time.time() - t0:.1f}s", file=sys.stderr)


if __name__ == "__main__":
    main()
