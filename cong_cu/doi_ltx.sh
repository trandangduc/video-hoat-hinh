#!/usr/bin/env bash
# DOI LTX — tat vLLM (qwen38 + qwen3-embedding), roi khoi dong ComfyUI + LTX de lam video.
# Song song 2 GPU: GPU0 :8188, GPU1 :8189
#
#   bash cong_cu/doi_ltx.sh                          # dung kich ban dang dung (logs/kich_ban_dang_dung.txt)
#   bash cong_cu/doi_ltx.sh vao/kich_ban_t2v.json    # dung kich ban cu the
#   bash cong_cu/doi_ltx.sh --canh canh_03           # chi render 1 canh
#   bash cong_cu/doi_ltx.sh --ghep                   # chi ghep (khong render)
#   bash cong_cu/doi_ltx.sh --comfy-chi              # chi bat ComfyUI, khong chay pipeline
#   bash cong_cu/doi_ltx.sh --gpu 1                  # chi dung GPU1
#   bash cong_cu/doi_ltx.sh --song-song              # bat buoc song song 2 GPU (mac dinh tu dong)
set -uo pipefail
D=${D:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}
cd "$D"

# --------------------------------------------------------------- doi so
KICH_BAN=""
CANH=""
GHEP_CHI=0
COMFY_CHI=0
GPU_CHI=""          # "0" hoac "1" de chi dung 1 GPU
SONG_SONG=0         # 1 = bat buoc song song 2 GPU
for a in "$@"; do
  case "$a" in
    --canh)   : ;;  # lay tham so tiep theo
    --ghep)   GHEP_CHI=1 ;;
    --comfy-chi) COMFY_CHI=1 ;;
    --gpu)    : ;;  # lay tham so tiep theo
    --song-song) SONG_SONG=1 ;;
    -*)       echo "khong biet tham so: $a"; exit 1 ;;
    *)
      if [ -z "$CANH" ] && [ -n "${PREV_CANH:-}" ]; then CANH="$a"; PREV_CANH=""
      elif [ -z "$GPU_CHI" ] && [ -n "${PREV_GPU:-}" ]; then GPU_CHI="$a"; PREV_GPU=""
      elif [ -z "$KICH_BAN" ]; then KICH_BAN="$a"
      else echo "thua tham so: $a"; exit 1; fi
      ;;
  esac
  [ "$a" = "--canh" ] && PREV_CANH=1
  [ "$a" = "--gpu" ] && PREV_GPU=1
done

# Kich ban mac dinh: doc tu logs/kich_ban_dang_dung.txt
if [ -z "$KICH_BAN" ] && [ ! "$GHEP_CHI" = "1" ]; then
  if [ -f logs/kich_ban_dang_dung.txt ]; then
    KICH_BAN=$(cat logs/kich_ban_dang_dung.txt | tr -d '[:space:]')
  else
    KICH_BAN="vao/kich_ban.json"
  fi
fi

say(){ echo "[$(date +%H:%M:%S)] $*"; }

# --------------------------------------------------------------- 1. TAT vLLM
say "=== 1/4 TAT vLLM (qwen38 + qwen3-embedding) ==="

# Tim PID theo port (an toan hon pkill — khong giet lan can)
tat_port(){
  local port=$1 ten=$2
  local pids
  pids=$(ss -ltnp 2>/dev/null | grep ":$port\b" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
  if [ -z "$pids" ]; then
    say "  $ten (:$port) khong chay"
    return 0
  fi
  for p in $pids; do
    say "  $ten (:$port) pid=$p -> kill"
    kill "$p" 2>/dev/null
  done
  # Chờ toi 30 giay cho VRAM nha
  local i
  for i in $(seq 1 30); do
    pids=$(ss -ltnp 2>/dev/null | grep ":$port\b" | grep -oE 'pid=[0-9]+' | cut -d= -f2 | sort -u)
    [ -z "$pids" ] && { say "  $ten da tat sau $i s"; return 0; }
    sleep 1
  done
  # Van con -> kill -9
  for p in $pids; do
    say "  $ten pid=$p van con -> kill -9"
    kill -9 "$p" 2>/dev/null
  done
  sleep 2
  say "  $ten da bat buoc tat"
}

tat_port 8000 "qwen38"
tat_port 8002 "qwen3-embedding"

# --------------------------------------------------------------- 2. DOI VRAM
say "=== 2/4 DOI VRAM nha ==="
for i in $(seq 1 30); do
  free0=$(nvidia-smi --id=0 --query-gpu=memory.free --format=csv,noheader,nounits)
  free1=$(nvidia-smi --id=1 --query-gpu=memory.free --format=csv,noheader,nounits)
  say "  GPU0: ${free0} MiB  GPU1: ${free1} MiB"
  # Ca 2 GPU deu co > 24 GB roi thi du
  if [ "$free0" -ge 24000 ] && [ "$free1" -ge 24000 ]; then
    say "  VRAM du roi"
    break
  fi
  [ "$i" = "30" ] && say "  CANH BAO: VRAM chua du sau 30s, tiep tuc..."
  sleep 2
done

# --------------------------------------------------------------- 3. BAT COMFYUI
# Xac dinh so GPU se dung
if [ -n "$GPU_CHI" ]; then
  # Chi 1 GPU duoc chi dinh
  GPU_LIST=("$GPU_CHI")
  PORT_LIST=()
  [ "$GPU_CHI" = "0" ] && PORT_LIST=(8188) || PORT_LIST=(8189)
  say "=== 3/4 BAT COMFYUI (GPU$GPU_CHI :${PORT_LIST[0]}) ==="
else
  # Mac dinh: song song 2 GPU neu VRAM du
  GPU_LIST=(0 1)
  PORT_LIST=(8188 8189)
  say "=== 3/4 BAT COMFYUI SONG SONG (GPU0 :8188, GPU1 :8189) ==="
fi

# Bat tung ComfyUI
PIDS_COMFY=()
for idx in "${!GPU_LIST[@]}"; do
  gpu=${GPU_LIST[idx]}
  port=${PORT_LIST[idx]}
  if curl -sf -m 2 "http://127.0.0.1:$port/system_stats" >/dev/null 2>&1; then
    say "  ComfyUI da chay san o :$port (GPU$gpu)"
  else
    say "  Khoi dong ComfyUI GPU$gpu :$port..."
    CUDA_VISIBLE_DEVICES=$gpu COMFY_PORT=$port bash cong_cu/comfy.sh len || { say "LOI: khong bat duoc ComfyUI GPU$gpu"; exit 1; }
  fi
  # Lay PID
  pid_file="$D/logs/comfy$([ "$port" = "8188" ] && echo "" || echo "_$port").pid"
  [ -f "$pid_file" ] && PIDS_COMFY+=("$(cat "$pid_file")")
done

if [ "$COMFY_CHI" = "1" ]; then
  say "=== COMFY-CHI: da bat ComfyUI, dung o day ==="
  exit 0
fi

# --------------------------------------------------------------- 4. CHAY PIPELINE
if [ "$GHEP_CHI" = "1" ]; then
  say "=== 4/4 GHEP VIDEO ==="
  .venv/bin/python scripts/03_ghep.py --kich-ban "$KICH_BAN" || { say "LOI khi ghep"; exit 1; }
else
  say "=== 4/4 RENDER VIDEO (kich ban: $KICH_BAN) ==="
  
  if [ -n "$CANH" ]; then
    # Chi 1 canh -> chay don
    .venv/bin/python scripts/02_hoat_hinh.py --kich-ban "$KICH_BAN" --canh "$CANH" --lam-lai \
      || { say "LOI render canh $CANH"; exit 1; }
  elif [ "${#GPU_LIST[@]}" -eq 2 ] && [ "$SONG_SONG" = "1" ] || [ "${#GPU_LIST[@]}" -eq 2 ] && [ -z "$GPU_CHI" ]; then
    # SONG SONG 2 GPU: chia canh cho 2 tien trinh
    say "  Chay song song tren 2 GPU..."
    
    # Lay danh sach canh tu kich ban
    CANH_LIST=$(.venv/bin/python3 -c "
import json, sys
kb = json.load(open('$KICH_BAN', encoding='utf-8'))
print(' '.join(c['id'] for c in kb['canh']))
")
    # Chia canh: le -> GPU0, chan -> GPU1
    CANH_GPU0=()
    CANH_GPU1=()
    i=0
    for c in $CANH_LIST; do
      if [ $((i % 2)) -eq 0 ]; then
        CANH_GPU0+=("$c")
      else
        CANH_GPU1+=("$c")
      fi
      i=$((i+1))
    done
    
    say "  GPU0 (port 8188): ${CANH_GPU0[*]}"
    say "  GPU1 (port 8189): ${CANH_GPU1[*]}"
    
    # Chay song song
    PIDS_RENDER=()
    
    if [ ${#CANH_GPU0[@]} -gt 0 ]; then
      CUDA_VISIBLE_DEVICES=0 .venv/bin/python scripts/02_hoat_hinh.py --kich-ban "$KICH_BAN" --canh "${CANH_GPU0[@]}" --lam-lai \
        > "$D/logs/render_gpu0.log" 2>&1 &
      PIDS_RENDER+=($!)
    fi
    
    if [ ${#CANH_GPU1[@]} -gt 0 ]; then
      CUDA_VISIBLE_DEVICES=1 .venv/bin/python scripts/02_hoat_hinh.py --kich-ban "$KICH_BAN" --canh "${CANH_GPU1[@]}" --lam-lai \
        > "$D/logs/render_gpu1.log" 2>&1 &
      PIDS_RENDER+=($!)
    fi
    
    # Doi ca 2 xong
    for pid in "${PIDS_RENDER[@]}"; do
      wait "$pid" || { say "LOI render (pid $pid)"; tail -20 "$D/logs/render_gpu0.log" "$D/logs/render_gpu1.log" 2>/dev/null; exit 1; }
    done
    
    say "  Da render xong ca 2 GPU"
  else
    # Don GPU
    .venv/bin/python scripts/02_hoat_hinh.py --kich-ban "$KICH_BAN" --lam-lai \
      || { say "LOI render"; exit 1; }
  fi
  
  say "=== GHEP VIDEO ==="
  .venv/bin/python scripts/03_ghep.py --kich-ban "$KICH_BAN" || { say "LOI khi ghep"; exit 1; }
fi

say "=== HOAN TAT ==="
