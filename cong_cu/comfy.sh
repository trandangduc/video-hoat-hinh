#!/usr/bin/env bash
# Bat / tat / xem ComfyUI. Ghim GPU theo bien CUDA_VISIBLE_DEVICES (mac dinh GPU0), cong theo COMFY_PORT.
# Chay 2 ban song song (moi GPU mot ban) de ve 2 canh cung luc:
#   bash cong_cu/comfy.sh len                                        # GPU0 :8188
#   CUDA_VISIBLE_DEVICES=1 COMFY_PORT=8189 bash cong_cu/comfy.sh len  # GPU1 :8189
# model_xuong.py chuyen hai service Qwen <-> ComfyUI theo nut Bam cua chu may.
# Script nay chi quan ly ComfyUI, khong tu tat cac dich vu khac.
set -uo pipefail
D=/home/ai_ductran/video-hoat-hinh
PORT=${COMFY_PORT:-8188}
GPU=${CUDA_VISIBLE_DEVICES:-0}
DUOI=$([ "$PORT" = "8188" ] && echo "" || echo "_$PORT")     # ban :8188 giu ten file cu
PID=$D/logs/comfy$DUOI.pid
LOG=$D/logs/comfy$DUOI.log

len() {
  if curl -sf -m 2 "http://127.0.0.1:$PORT/system_stats" >/dev/null 2>&1; then
    echo "ComfyUI da chay san o :$PORT"; return 0; fi
  # VRAM trong tren GPU da chon -> chon che do nap
  # CHE_DO dat tay bang bien VRAM= thi khong tu do nua (--novram va --lowvram
  # loai tru nhau, ComfyUI bao loi neu dua ca hai).
  if [ -n "${VRAM:-}" ]; then
    CHE_DO="--$VRAM"
  else
    free=$(nvidia-smi --id=$GPU --query-gpu=memory.free --format=csv,noheader,nounits)
    # Vua tat ban cu thi VRAM chua nha kip -> doi toi 20 giay, khong thi len nham --lowvram (da gap 11/09)
    for i in $(seq 1 10); do
      [ "$free" -ge 24000 ] && break
      sleep 2; free=$(nvidia-smi --id=$GPU --query-gpu=memory.free --format=csv,noheader,nounits)
    done
    # Ban ComfyUI nay KHONG co --normalvram (chi gpu-only/highvram/lowvram/
    # novram/cpu). De TRONG = che do mac dinh, dung cho khi VRAM roi rai.
    if   [ "$free" -ge 24000 ]; then CHE_DO=""
    elif [ "$free" -ge 10000 ]; then CHE_DO=--lowvram
    else CHE_DO=--novram; fi
  fi
  # SageAttention: do duoc 1,11x, chat luong khong khac (xem logs/kiem/so/s_sage.png).
  # Tat bang SAGE=0. KHONG dung "--fast fp8_matrix_mult": do duoc no CHAM hon 0,88x
  # va an them 2,5 GB VRAM.
  SAGE_ARG=""
  [ "${SAGE:-1}" = "1" ] && SAGE_ARG="--use-sage-attention"
  # Bo nho ghim (pinned memory, mac dinh cua ComfyUI) giu ban sao trong so trong RAM: do 11/09 RSS an danh
  # 40 GB/ban -> 2 ban vuot 60 GB RAM. Tat di: 5 GB/ban. Bat lai bang PIN=1.
  PIN_ARG="--disable-pinned-memory"
  [ "${PIN:-0}" = "1" ] && PIN_ARG=""
  echo "GPU$GPU :$PORT con ${free:-?} MiB -> $CHE_DO $SAGE_ARG $PIN_ARG ${COMFY_THEM:-}"
  cd "$D/ComfyUI"
  CUDA_VISIBLE_DEVICES=$GPU nohup .venv/bin/python main.py \
     --listen 127.0.0.1 --port "$PORT" $CHE_DO --preview-method none $SAGE_ARG $PIN_ARG ${COMFY_THEM:-} \
     > "$LOG" 2>&1 &
  echo $! > "$PID"
  echo "dang khoi dong (pid $(cat $PID)), log: $LOG"
  for i in $(seq 1 60); do
    sleep 5
    curl -sf -m 2 "http://127.0.0.1:$PORT/system_stats" >/dev/null 2>&1 && {
      echo "ComfyUI :$PORT len sau $((i*5))s"; return 0; }
    kill -0 "$(cat $PID)" 2>/dev/null || { echo "CHET luc khoi dong:"; tail -20 "$LOG"; return 1; }
  done
  echo "qua 300s chua len"; tail -20 "$LOG"; return 1
}

tat() {
  # Chi tat DUNG ban o cong nay (truoc day pkill ca may -> giet luon ban GPU kia).
  local p=""
  [ -f "$PID" ] && p=$(cat "$PID")
  kill -0 "$p" 2>/dev/null || p=$(ss -ltnp 2>/dev/null | grep ":$PORT\b" | grep -oE "pid=[0-9]+" | head -1 | cut -d= -f2)
  [ -n "$p" ] && kill "$p" 2>/dev/null
  for i in $(seq 1 20); do ss -ltn | grep -q ":$PORT\b" || break; sleep 0.5; done
  rm -f "$PID"; echo "da tat ComfyUI :$PORT"
}

case "${1:-len}" in
  len|start) len ;;
  tat|stop)  tat ;;
  log)       tail -f "$LOG" ;;
  trang_thai|status)
             curl -sf -m 3 "http://127.0.0.1:$PORT/system_stats" | python3 -m json.tool 2>/dev/null \
               || echo "khong chay" ;;
esac
