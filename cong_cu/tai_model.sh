#!/usr/bin/env bash
# Tai model Wan 2.2 tu HuggingFace ve models/. Chay lai duoc: da co du byte thi bo qua,
# tai do dang thi -C - tiep tuc. In tien do moi file (luat cung #6).
set -uo pipefail
D=/home/ai_ductran/video-hoat-hinh
BASE=https://huggingface.co/Comfy-Org/Wan_2.2_ComfyUI_Repackaged/resolve/main/split_files
say() { echo "[$(date +%H:%M:%S)] $*"; }

# dich|duong dan tren repo|so byte mong doi
FILES=(
"models/diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors|diffusion_models/wan2.2_s2v_14B_fp8_scaled.safetensors|16394821672"
"models/text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors|text_encoders/umt5_xxl_fp8_e4m3fn_scaled.safetensors|0"
"models/vae/wan2.2_vae.safetensors|vae/wan2.2_vae.safetensors|0"
"models/audio_encoders/wav2vec2_large_english_fp16.safetensors|audio_encoders/wav2vec2_large_english_fp16.safetensors|0"
"models/diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors|diffusion_models/wan2.2_i2v_high_noise_14B_fp8_scaled.safetensors|0"
"models/diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors|diffusion_models/wan2.2_i2v_low_noise_14B_fp8_scaled.safetensors|0"
)
T0=$(date +%s)
for row in "${FILES[@]}"; do
  IFS='|' read -r dest path _ <<< "$row"
  out="$D/$dest"
  url="$BASE/$path"
  remote=$(curl -sIL "$url" | awk 'BEGIN{IGNORECASE=1}/^content-length:/{v=$2}END{gsub(/\r/,"",v);print v}')
  local_sz=$(stat -c%s "$out" 2>/dev/null || echo 0)
  if [ -n "$remote" ] && [ "$local_sz" = "$remote" ]; then
    say "BO QUA (du roi): $(basename "$out")  $((local_sz/1048576)) MB"; continue
  fi
  say "TAI: $(basename "$out")  ($((remote/1048576)) MB)  da co $((local_sz/1048576)) MB"
  curl -L -C - --retry 5 --retry-delay 5 --retry-all-errors -# -o "$out" "$url" 2>&1 | tr '\r' '\n' | awk 'NR%40==0'
  say "XONG: $(basename "$out")  $(stat -c%s "$out" 2>/dev/null | awk '{printf "%.2f GB", $1/1073741824}')"
done
say "TAT CA XONG sau $(( ($(date +%s)-T0)/60 )) phut"
du -sh "$D/models"
