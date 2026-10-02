#!/usr/bin/env bash
# Render CUNG mot canh, cung seed, khac so buoc / do phan giai -> giu lai tung
# clip de so chat luong bang mat. Toc do da do o do_toc_do.sh.
set -uo pipefail
D=/home/ai_ductran/video-hoat-hinh; cd "$D"
mkdir -p logs/kiem/so
for c in "20 832 480" "12 832 480" "8 832 480" "8 640 384"; do
  set -- $c
  ten="${1}buoc_${2}x${3}"
  echo "######## $ten ########"
  CUDA_VISIBLE_DEVICES=0 .venv/bin/python scripts/02_hoat_hinh.py \
    --canh canh_01 --lam-lai --buoc-lay "$1" --rong "$2" --cao "$3" \
    --do "logs/ab_${ten}.json" 2>&1 | grep -E "render xong"
  cp ra/clip/canh_01.mp4 "logs/kiem/so/${ten}.mp4"
done
echo "xong, clip nam o logs/kiem/so/"
