#!/usr/bin/env bash
# T2V thuan (khong anh mau) 5 canh Dyatlov bang LTX-2.5 dev int8, roi ghep.
set -uo pipefail
cd /home/ai_ductran/video-hoat-hinh
KB=vao/kich_ban_t2v_full.json
T0=$(date +%s)
echo "=========== T2V 5 canh  ($(date +%H:%M:%S)) ==========="
.venv/bin/python scripts/02_hoat_hinh.py --kich-ban "$KB" --lam-lai || { echo "LOI buoc hinh"; exit 1; }
echo "=========== GHEP  ($(date +%H:%M:%S)) ==========="
.venv/bin/python scripts/03_ghep.py --kich-ban "$KB" --ra ra/video_t2v_full.mp4 || { echo "LOI khi ghep"; exit 1; }
echo "=========== HOAN TAT sau $(( ($(date +%s)-T0)/60 )) phut ==========="
