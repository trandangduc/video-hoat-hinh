#!/usr/bin/env bash
# Tai bo LTX-2.5 ban goc bf16 (khong nen) + cac phan con thieu.
set -uo pipefail
D=/home/ai_ductran/video-hoat-hinh
TK=$(cat ~/.cache/huggingface/token | tr -d '\n')
B=https://huggingface.co/Lightricks/LTX-2.5/resolve/main

tai() {  # $1 = duong dan trong repo, $2 = thu muc dich
  local f="$1" dir="$D/models/$2" name out url mong co
  name=$(basename "$f"); out="$dir/$name"; url="$B/$f"
  mkdir -p "$dir"
  mong=$(curl -sIL -H "Authorization: Bearer $TK" "$url" | awk 'BEGIN{IGNORECASE=1}/^content-length:/{v=$2}END{gsub(/\r/,"",v);print v}')
  if [ "$(stat -c%s "$out" 2>/dev/null || echo 0)" = "$mong" ]; then
    echo "[$(date +%H:%M:%S)] da co  $name"; return 0; fi
  echo "[$(date +%H:%M:%S)] TAI   $name  ($((mong/1048576)) MB)"
  curl -L --retry 5 --retry-all-errors -H "Authorization: Bearer $TK" -o "$out" "$url" 2>/dev/null
  co=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ "$co" = "$mong" ]; then
    echo "[$(date +%H:%M:%S)] OK    $name  $(awk -v b=$co 'BEGIN{printf "%.2f GB",b/1073741824}')"
  else
    echo "[$(date +%H:%M:%S)] LOI   $name  $co / $mong byte"; return 1; fi
}

# nho truoc -> thay ket qua som
tai model_patches/ltx-2.5-duration-head-bf16.safetensors                    model_patches
tai latent_upscale_models/ltx-2.5-latent-temporal-upscaler-x2-bf16-1.0.safetensors latent_upscale_models
tai vae/ltx-2.5-video-vae-conv-bf16.safetensors                             vae
tai text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors             text_encoders
tai diffusion_models/ltx-2.5-22b-dev-transformer-bf16.safetensors           diffusion_models
echo "[$(date +%H:%M:%S)] XONG HET"
