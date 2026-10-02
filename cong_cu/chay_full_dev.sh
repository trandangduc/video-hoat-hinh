#!/usr/bin/env bash
# Lam lai canh_02..05 bang LTX-2.5 dev int8 (canh_01 da xong), roi ghep video cuoi.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
T0=$(date +%s)
for c in canh_02 canh_03 canh_04 canh_05; do
  echo "=========== $c  ($(date +%H:%M:%S)) ==========="
  .venv/bin/python scripts/02_hoat_hinh.py --canh "$c" --lam-lai || {
    echo "LOI o $c -- dung lai"; exit 1; }
done
echo "=========== GHEP  ($(date +%H:%M:%S)) ==========="
.venv/bin/python scripts/03_ghep.py || { echo "LOI khi ghep"; exit 1; }
echo "=========== HOAN TAT sau $(( ($(date +%s)-T0)/60 )) phut ==========="
