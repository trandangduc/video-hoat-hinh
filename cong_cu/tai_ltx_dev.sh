#!/usr/bin/env bash
# Tai ban DEV cua LTX-2.5 (khong distilled). Nhieu buoc lay mau hon -> it nhieu hon.
set -uo pipefail
D=${D:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
TK=$(cat ~/.cache/huggingface/token | tr -d '\n')
out="$D/models/diffusion_models/ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors"
url="https://huggingface.co/Lightricks/LTX-2.5/resolve/main/diffusion_models/ltx-2.5-22b-dev-transformer-comfy-int8-convrot.safetensors"
mong=$(curl -sIL -H "Authorization: Bearer $TK" "$url" | awk 'BEGIN{IGNORECASE=1}/^content-length:/{v=$2}END{gsub(/\r/,"",v);print v}')
if [ "$(stat -c%s "$out" 2>/dev/null || echo 0)" = "$mong" ]; then echo "da co du roi"; exit 0; fi
rm -f "$out"
echo "[$(date +%H:%M:%S)] TAI ban dev ($((mong/1048576)) MB)"
curl -sL --retry 5 --retry-all-errors -H "Authorization: Bearer $TK" -o "$out" "$url"
co=$(stat -c%s "$out" 2>/dev/null || echo 0)
[ "$co" = "$mong" ] && echo "[$(date +%H:%M:%S)] OK $(awk -v b=$co 'BEGIN{printf "%.2f GB",b/1073741824}')" \
                    || echo "[$(date +%H:%M:%S)] LOI: $co / $mong byte"
