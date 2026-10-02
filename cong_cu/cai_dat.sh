#!/usr/bin/env bash
# Cai toan bo moi truong cho pipeline. Chay lai duoc nhieu lan.
set -uo pipefail
D=/home/ai_ductran/video-hoat-hinh
export PATH=$HOME/.local/bin:$PATH
export UV_HTTP_TIMEOUT=300
say() { echo; echo "=========== [$(date +%H:%M:%S)] $* ==========="; }
cd "$D"

say "1/5  torch cu128 (sm_120) cho venv TTS"
uv pip install --python "$D/.venv/bin/python" \
   --index-url https://download.pytorch.org/whl/cu128 \
   torch torchvision torchaudio 2>&1 | tail -5

say "2/5  chatterbox-tts (ep torch >=2.7)"
uv pip install --python "$D/.venv/bin/python" \
   --overrides "$D/cong_cu/ep_torch.txt" \
   chatterbox-tts 2>&1 | tail -15

say "3/5  thu vien cho giao dien + ghep video"
uv pip install --python "$D/.venv/bin/python" \
   fastapi "uvicorn[standard]" python-multipart requests pillow soundfile 2>&1 | tail -3

say "4/5  ffmpeg static (khong co sudo nen khong apt duoc)"
if [ ! -x "$D/cong_cu/bin/ffmpeg" ]; then
  mkdir -p "$D/cong_cu/bin" /tmp/ffdl && cd /tmp/ffdl
  curl -sL -o ff.tar.xz https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz
  tar xf ff.tar.xz && cp ffmpeg-*-static/ffmpeg ffmpeg-*-static/ffprobe "$D/cong_cu/bin/"
  cd "$D" && rm -rf /tmp/ffdl
fi
"$D/cong_cu/bin/ffmpeg" -version 2>&1 | head -1

say "5/5  ComfyUI + node GGUF + venv rieng"
cd "$D"
[ -d ComfyUI ] || git clone --depth 1 https://github.com/comfyanonymous/ComfyUI.git 2>&1 | tail -2
cd ComfyUI
[ -d .venv ] || uv venv --python 3.12 .venv 2>&1 | tail -1
uv pip install --python .venv/bin/python \
   --index-url https://download.pytorch.org/whl/cu128 \
   torch torchvision torchaudio 2>&1 | tail -3
uv pip install --python .venv/bin/python -r requirements.txt 2>&1 | tail -5
mkdir -p custom_nodes && cd custom_nodes
[ -d ComfyUI-GGUF ] || git clone --depth 1 https://github.com/city96/ComfyUI-GGUF.git 2>&1 | tail -2
[ -d ComfyUI-VideoHelperSuite ] || git clone --depth 1 https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git 2>&1 | tail -2
cd "$D/ComfyUI"
uv pip install --python .venv/bin/python gguf 2>&1 | tail -2

say "XONG CAI DAT"
