#!/usr/bin/env bash
# Xem tien do + thoi gian cua mot lan chay.
#   bash cong_cu/tien_do.sh                 # log moi nhat, cac moc chinh
#   bash cong_cu/tien_do.sh -t              # bam theo thoi gian thuc
#   bash cong_cu/tien_do.sh logs/abc.log    # chi ro file log
cd "$(dirname "${BASH_SOURCE[0]}")/.."
theo=0; log=""
for a in "$@"; do case "$a" in -t) theo=1;; *) log="$a";; esac; done
# Khong chi ro thi lay log RENDER moi nhat (bo comfy.log va log tai model)
[ -z "$log" ] && log=$(ls -t logs/*.log 2>/dev/null \
  | grep -vE "comfy\.log|tai_.*\.log|server.*\.log|vram_" | head -1)
[ -f "$log" ] || { echo "Khong thay log nao."; exit 1; }

echo "== $log"
if [ "$theo" = 1 ]; then
  tail -f "$log"; exit 0
fi

grep -E "^\[ *[0-9.]+s\] (==|   render xong|   ->|   LOI)" "$log" | sed 's/^/  /'
echo
# Dong cuoi cung cho biet dang o dau
echo "  dang o: $(tail -1 "$log")"
# Con chay khong
if pgrep -f "0[2]_hoat_hinh|0[13]_" >/dev/null 2>&1; then
  echo "  -> VAN DANG CHAY"
else
  echo "  -> da dung"
fi
