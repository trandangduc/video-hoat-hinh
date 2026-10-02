#!/usr/bin/env bash
# Tai LTX-2.5 22B NVFP4 tu repo chinh thuc (gated - can token co quyen
# "Read contents of public gated repos").
#
# KHONG dung `curl -C -`: lan truoc resume da NOI THEM vao file do dang cua
# lan bi cat ngang, lam file phinh to hon kich thuoc that va vo header. Tai lai
# tu dau an toan hon nhieu so voi tiet kiem vai phut.
set -uo pipefail
D=${D:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
TK=$(cat ~/.cache/huggingface/token | tr -d '\n')
say(){ echo "[$(date +%H:%M:%S)] $*"; }

# duong dan tren repo | thu muc dich | so byte mong doi
DS="
Lightricks/LTX-2.5|vae/ltx-2.5-audio-vae-bf16.safetensors|vae|364866540
Lightricks/LTX-2.5|vae/ltx-2.5-video-vae-bf16.safetensors|vae|1472223346
Lightricks/LTX-2.5|latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors|latent_upscale_models|995778752
Comfy-Org/gemma-4|text_encoders/gemma4_e2b_it_int8_convrot.safetensors|text_encoders|0
Lightricks/LTX-2.5|text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors|text_encoders|15372969374
Lightricks/LTX-2.5|diffusion_models/ltx-2.5-22b-distilled-transformer-nvfp4.safetensors|diffusion_models|18721548408
"
T0=$(date +%s); LOI=0
echo "$DS" | while IFS='|' read -r repo path thu_muc mong; do
  [ -z "$repo" ] && continue
  ten=$(basename "$path"); out="$D/models/$thu_muc/$ten"
  url="https://huggingface.co/$repo/resolve/main/$path"
  mkdir -p "$D/models/$thu_muc"
  [ "$mong" = "0" ] && mong=$(curl -sIL -H "Authorization: Bearer $TK" "$url" \
      | awk 'BEGIN{IGNORECASE=1}/^content-length:/{v=$2}END{gsub(/\r/,"",v);print v}')
  if [ "$(stat -c%s "$out" 2>/dev/null || echo 0)" = "$mong" ]; then
    say "BO QUA (du roi): $ten"; continue
  fi
  rm -f "$out"
  say "TAI $ten  ($((mong/1048576)) MB)"
  curl -sL --retry 5 --retry-delay 5 --retry-all-errors \
       -H "Authorization: Bearer $TK" -o "$out" "$url"
  co=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$co" = "$mong" ]; then say "  OK $(awk -v b=$co 'BEGIN{printf "%.2f GB",b/1073741824}')"
  else say "  LOI: $co / $mong byte"; fi
done
say "XONG sau $(( ($(date +%s)-T0)/60 )) phut"
