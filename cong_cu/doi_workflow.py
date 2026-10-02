"""Doi workflow ComfyUI tu dinh dang GIAO DIEN sang dinh dang API.

ComfyUI luu workflow theo hai dinh dang khac han nhau:
  - giao dien: {"nodes":[{id,type,widgets_values,inputs,outputs}], "links":[...]}
  - API      : {"<id>": {"class_type":..., "inputs":{ten: gia_tri | [nguon, slot]}}}

Ban mau chinh thuc cua LTX-2.5 con boc toan bo do thi trong mot SUBGRAPH, nen
phai mo no ra truoc. Script nay lam ca hai viec.

  python cong_cu/doi_workflow.py <file giao dien> --ra workflows/ltx.json
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

MAY = "http://127.0.0.1:8188"


def object_info() -> dict:
    with urllib.request.urlopen(f"{MAY}/object_info", timeout=60) as r:
        return json.loads(r.read())


def ten_dau_vao(spec: dict) -> tuple[list[str], set[str]]:
    """Tra ve (thu tu ten dau vao, tap ten la 'o dien' tren giao dien).

    O dien = kieu vo huong (INT/FLOAT/STRING/BOOLEAN/COMBO) -> gia tri nam
    trong widgets_values theo DUNG THU TU nay. Cac dau vao con lai la day noi.
    """
    thu_tu, o_dien = [], set()
    inp = spec.get("input", {})
    for nhom in ("required", "optional"):
        for ten, v in (inp.get(nhom) or {}).items():
            thu_tu.append(ten)
            kieu = v[0] if isinstance(v, list) and v else v
            if isinstance(kieu, list) or kieu in ("INT", "FLOAT", "STRING", "BOOLEAN", "COMBO"):
                o_dien.add(ten)
    return thu_tu, o_dien


def mo_subgraph(d: dict) -> tuple[list, list]:
    """Neu do thi chi la mot subgraph thi lay do thi ben trong ra."""
    sg = (d.get("definitions") or {}).get("subgraphs") or []
    if not sg:
        return d.get("nodes", []), d.get("links", [])
    g = sg[0]
    print(f"  mo subgraph '{g.get('name')}': {len(g.get('nodes', []))} node", file=sys.stderr)
    return g.get("nodes", []), g.get("links", [])


def doi(d: dict, oi: dict) -> dict:
    nodes, links = mo_subgraph(d)

    # link_id -> (node nguon, slot nguon)
    nguon = {}
    for L in links:
        if isinstance(L, dict):
            nguon[L["id"]] = (str(L["origin_id"]), L["origin_slot"])
        elif len(L) >= 4:
            nguon[L[0]] = (str(L[1]), L[2])

    bo_qua = {"MarkdownNote", "Note", "Reroute", "PreviewAny", "PrimitiveNode"}
    api, thieu = {}, []
    for n in nodes:
        t = n.get("type", "")
        if t in bo_qua or t.startswith("workflow>"):
            continue
        spec = oi.get(t)
        if spec is None:
            thieu.append(t)
            continue
        thu_tu, o_dien = ten_dau_vao(spec)

        # 1) widgets_values ung voi TAT CA o dien, theo dung thu tu.
        #
        # BAY: khi subgraph "nang" mot o dien len thanh dau vao cua no, o do van
        # con nguyen gia tri trong widgets_values. Bo qua no roi don cac gia tri
        # sau len la LECH MOT NAC -- da dinh: CLIPLoader nhan type="...safetensors"
        # con device="ltxv". Nen phai do het truoc, roi moi de day noi de len.
        vao = {}
        wv = list(n.get("widgets_values") or [])
        for ten, gt in zip([x for x in thu_tu if x in o_dien], wv):
            vao[ten] = gt

        # 2) day noi de len o dien (chi nhan day tu node THAT; "-10" la cong vao
        #    cua subgraph, sau khi mo ra thi khong con nguon nen giu gia tri o dien)
        for i in n.get("inputs", []) or []:
            ten, lid = i.get("name"), i.get("link")
            if lid is None or ten not in thu_tu:
                continue
            src = nguon.get(lid)
            if src and not src[0].startswith("-"):
                vao[ten] = list(src)

        api[str(n["id"])] = {"class_type": t, "inputs": vao}

    if thieu:
        print(f"  CANH BAO: khong biet node {sorted(set(thieu))}", file=sys.stderr)
    return api


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("nguon")
    p.add_argument("--ra", required=True)
    a = p.parse_args()

    d = json.loads(Path(a.nguon).read_text(encoding="utf-8"))
    api = doi(d, object_info())
    Path(a.ra).write_text(json.dumps(api, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  -> {a.ra}  ({len(api)} node)", file=sys.stderr)
    for i, (k, v) in enumerate(api.items()):
        if i < 8:
            print(f"     {k:<6} {v['class_type']}", file=sys.stderr)


if __name__ == "__main__":
    main()
