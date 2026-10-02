#!/usr/bin/env bash
# Xem moi thu dang chay o mot cho.  Chay:  bash cong_cu/theo_doi.sh
# Them -l de lap lai moi 5 giay:        bash cong_cu/theo_doi.sh -l
D=/home/ai_ductran/video-hoat-hinh
xem() {
  echo "================ $(date '+%H:%M:%S') ================"
  echo "-- GPU --"
  nvidia-smi --query-gpu=index,memory.used,memory.total,utilization.gpu \
             --format=csv,noheader | sed 's/^/   GPU/'
  echo "   ai dang chiem:"
  nvidia-smi --query-compute-apps=pid,used_memory --format=csv,noheader | while read -r pid mem; do
    p=${pid%,}; u=$(ps -o user= -p "$p" 2>/dev/null | tr -d ' ')
    printf "     %-8s %-14s %s\n" "$p" "${u:-?}" "$mem"
  done

  echo "-- TAI MODEL --"
  if pgrep -f "tai_ltx.sh|tai_model.sh" >/dev/null; then
    echo "   dang tai:"; tail -2 "$D/logs/tai_ltx.log" 2>/dev/null | sed 's/^/     /'
    du -sh "$D/models" 2>/dev/null | sed 's/^/     tong: /'
  else
    echo "   khong tai gi"; du -sh "$D/models" 2>/dev/null | sed 's/^/     tong: /'
  fi

  echo "-- COMFYUI --"
  if curl -sf -m 2 http://127.0.0.1:8188/system_stats >/dev/null 2>&1; then
    q=$(curl -s -m 2 http://127.0.0.1:8188/queue | python3 -c \
        "import json,sys;d=json.load(sys.stdin);print('dang chay',len(d.get('queue_running',[])),'| xep hang',len(d.get('queue_pending',[])))" 2>/dev/null)
    echo "   dang chay o :8188   $q"
    tr '\r' '\n' < "$D/logs/comfy.log" 2>/dev/null | grep -E "[0-9]+%\|" | tail -1 | sed 's/^/     /'
  else
    echo "   khong chay"
  fi

  echo "-- KET QUA --"
  printf "   tieng %s file · clip %s file · video cuoi: %s\n" \
    "$(ls "$D"/ra/tieng/*.wav 2>/dev/null | wc -l)" \
    "$(ls "$D"/ra/clip/*.mp4 2>/dev/null | wc -l)" \
    "$([ -f "$D/ra/video_cuoi.mp4" ] && echo co || echo chua)"
  echo "-- DIA --"; df -h / | tail -1 | awk '{print "   con trong",$4,"("$5" da dung)"}'
}
if [ "${1:-}" = "-l" ]; then while :; do clear; xem; sleep 5; done; else xem; fi
