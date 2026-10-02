#!/usr/bin/env bash
# =====================================================================
#  Serve Qwen3-Embedding-8B (dim 4096) qua vLLM -> endpoint OpenAI /v1
#  cho retrieval cua app Fab9 Chat (.env: EMBED_MODEL=qwen3-embedding,
#  EMBED_API_BASE=http://127.0.0.1:8002/v1).
#
#  Ghim GPU1 (CUDA_VISIBLE_DEVICES=1); qwen36 dung GPU0.
#  max-model-len 8192: default 40960 OOM luc profiling.
#
#  Chay:  bash run_vllm_embed.sh
#  Doi:   "Uvicorn running on ... :8002" ; curl http://127.0.0.1:8002/v1/models
# =====================================================================
set -e

export HF_HOME=${HF_HOME:-/shared/hf_duc}
export HF_HUB_OFFLINE=1
export CUDA_HOME=/usr/local/cuda
export PATH=/home/ai_ductran/vrag/.venv/bin:$CUDA_HOME/bin:$PATH
export CUDA_DEVICE_ORDER=PCI_BUS_ID
export CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-1}   # GPU1 cho embed; GPU0 cho qwen36
# Gioi han job compile song song cua JIT (xem giai thich dai trong run_vllm_qwen36.sh):
# ninja -j mac dinh = so CPU -> co the an het RAM may -> OOM killer giet service.
export MAX_JOBS=${MAX_JOBS:-4}

MODEL=${MODEL:-Qwen/Qwen3-Embedding-8B}
PORT=${PORT:-8002}

# EMBED_QUANT: de TRONG = giu nguyen bf16 (~15,3 GiB trong so) nhu tu truoc.
# Dat EMBED_QUANT=fp8 -> vLLM quant online xuong ~8,5 GiB, nhuong ~7 GiB tren
# GPU1 cho shard TP=2 cua model chat 27B (xem run_vllm_qwen38.sh).
# CANH BAO: doi luong tu la doi VECTOR. Vector cau hoi phai cung khong gian voi
# vector tai lieu da nam trong index -> sau khi doi phai chay
# scripts/test_bkm_retrieval.py; lech diem thi rebuild index (build_index()).
QUANT_ARG=()
[ -n "${EMBED_QUANT:-}" ] && QUANT_ARG=(--quantization "$EMBED_QUANT")

exec /home/ai_ductran/vrag/.venv/bin/vllm serve "$MODEL" \
  --runner pooling \
  --served-model-name qwen3-embedding \
  --host 0.0.0.0 --port "$PORT" \
  --tensor-parallel-size 1 \
  --max-model-len 8192 \
  "${QUANT_ARG[@]}" \
  --gpu-memory-utilization ${GPU_UTIL:-0.85}
