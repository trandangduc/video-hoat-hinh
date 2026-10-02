#!/usr/bin/env bash
# Do A/B: doi so buoc lay mau va do phan giai anh huong the nao den thoi gian.
# Dung CUNG mot canh, cung seed -> khac biet chi den tu tham so.
set -uo pipefail
D=/home/ai_ductran/video-hoat-hinh
cd "$D"
for c in "20 832 480" "12 832 480" "8 832 480" "20 640 384"; do
  set -- $c
  echo; echo "######## $1 buoc, $2x$3 ########"
  CUDA_VISIBLE_DEVICES=0 .venv/bin/python scripts/02_hoat_hinh.py \
    --canh canh_01 --lam-lai --buoc-lay "$1" --rong "$2" --cao "$3" \
    --do "logs/ab_${1}b_${2}x${3}.json" 2>&1 | grep -E "render xong|VRAM:|khung ="
done
