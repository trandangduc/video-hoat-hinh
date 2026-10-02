"""Switch the two GPUs between existing Qwen services and optimized ComfyUI.

Transitions run detached from HTTP; only fixed, allowlisted services are controlled.
Shared usage leases prevent stopping a model while a workshop operation is using it.
"""
from __future__ import annotations
import fcntl
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / 'logs/model_xuong.json'
LOCK = ROOT / 'logs/model_xuong.lock'
USE = ROOT / 'logs/model_xuong_use.lock'
RUN = ROOT / 'logs/model_xuong_run.lock'
SERVICES = ('vllm-qwen38.service', 'vllm-embed.service')
PORTS = (8188, 8189)
TRANSITIONS = ('starting', 'stopping', 'restoring')
BOOT = Path('/proc/sys/kernel/random/boot_id').read_text().strip()


@contextmanager
def lock(path=None, shared=False, nonblocking=False):
    with open(path or LOCK, 'a') as handle:
        flags = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        try:
            fcntl.flock(handle, flags | (fcntl.LOCK_NB if nonblocking else 0))
        except BlockingIOError:
            raise RuntimeError('Xưởng đang sử dụng model hoặc đang chuyển chế độ. Đợi công việc hoàn tất.')
        try:
            yield handle
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def read():
    if not STATE.exists():
        return {'phase': 'off', 'message': 'ComfyUI chưa bật', 'error': ''}
    return json.loads(STATE.read_text())


def write(**changes):
    data = {**read(), **changes, 'updated': time.time(), 'boot': BOOT}
    fd, name = tempfile.mkstemp(prefix='.model-', dir=STATE.parent)
    try:
        with os.fdopen(fd, 'w') as out:
            json.dump(data, out, ensure_ascii=False)
            out.flush(); os.fsync(out.fileno())
        os.replace(name, STATE)
    finally:
        Path(name).unlink(missing_ok=True)
    return data


def transition_alive(state):
    try:
        cmd = Path(f"/proc/{int(state['pid'])}/cmdline").read_bytes().split(b'\0')
        return str(Path(__file__).resolve()).encode() in cmd and str(state['operation']).encode() in cmd
    except (OSError, ValueError, KeyError):
        return False


def healthy(port, path='/system_stats'):
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=2) as response:
            data = json.load(response)
            return bool(data.get('devices')) if path == '/system_stats' else bool(data.get('data'))
    except Exception:
        return False


def status():
    state = read()
    if state.get('phase') == 'video' and state.get('boot') != BOOT:
        state = {**state, 'phase': 'error', 'error': 'Máy vừa khởi động lại. Bấm Bật ComfyUI để chuyển lại 2 GPU.'}
    if state.get('phase') in TRANSITIONS and not transition_alive(state):
        state = {**state, 'phase': 'error', 'error': 'Tiến trình chuyển model bị gián đoạn. Bấm Bật hoặc Dừng để thử lại.'}
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(healthy, p, '/system_stats' if p in PORTS else '/v1/models') for p in (*PORTS, 8000, 8002)]
        checks = [f.result() for f in futures]
    state['comfy'] = checks[:2]
    state['qwen'] = checks[2:]
    state['ready'] = state.get('phase') == 'video' and all(checks[:2]) and not any(checks[2:])
    state['busy'] = state.get('phase') in TRANSITIONS
    return state


@contextmanager
def lease():
    with lock(USE, shared=True, nonblocking=True):
        if not allowed():
            raise RuntimeError('Hãy bấm Bật ComfyUI · 2 GPU và đợi sẵn sàng trước khi tạo video.')
        yield


def allowed():
    state = read()
    return state.get('phase') == 'video' and state.get('boot') == BOOT


def request(action, busy_check=lambda: False):
    if action not in ('start', 'stop'):
        raise ValueError('Thao tác không hợp lệ.')
    with lock(USE, nonblocking=True), lock():
        state = read()
        if state.get('phase') in TRANSITIONS and transition_alive(state):
            raise RuntimeError('Đang chuyển model, vui lòng đợi hoàn tất.')
        if busy_check():
            raise RuntimeError('Xưởng còn cảnh, merge hoặc tác vụ AI đang chạy/chờ. Đợi xong hoặc huỷ hàng đợi trước.')
        operation = uuid.uuid4().hex
        write(phase='starting' if action == 'start' else 'stopping', operation=operation,
              message='Đang chuyển sang ComfyUI 2 GPU' if action == 'start' else 'Đang dừng ComfyUI và khôi phục Qwen',
              error='', pid=None)
        try:
            with open(ROOT / 'logs/model_xuong.log', 'ab') as log:
                proc = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), action, operation], cwd=ROOT,
                                        stdout=log, stderr=log, start_new_session=True)
            return write(pid=proc.pid)
        except Exception as e:
            write(phase='error', error=str(e), message='Không khởi động được tiến trình chuyển model')
            raise


def service(action, names=SERVICES):
    subprocess.run(['systemctl', '--user', action, *names], check=True, timeout=240)


def wait_health(port, timeout=1200):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if healthy(port, '/v1/models'):
            return
        time.sleep(3)
    raise RuntimeError(f'Model ở cổng {port} chưa sẵn sàng sau {timeout} giây; xem nhật ký systemd.')


def start_comfy():
    # Preserve SageAttention, default VRAM mode and disabled pinned memory in comfy.sh.
    for gpu, port in enumerate(PORTS):
        write(message=f'Đang khởi động ComfyUI trên GPU{gpu} ({gpu + 1}/2)')
        env = {**os.environ, 'CUDA_VISIBLE_DEVICES': str(gpu), 'COMFY_PORT': str(port)}
        for variable in ('VRAM', 'COMFY_THEM', 'PIN', 'SAGE'):
            env.pop(variable, None)
        subprocess.run(['bash', str(ROOT / 'cong_cu/comfy.sh'), 'len'], env=env, check=True, timeout=360)
        if not healthy(port):
            raise RuntimeError(f'ComfyUI GPU{gpu} chưa sẵn sàng.')


def comfy_pids(port):
    """Match exact ComfyUI working directory + command, never kill a port's arbitrary owner."""
    found = []
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            cmd = (proc / 'cmdline').read_bytes().decode().split('\0')
            if (proc / 'cwd').resolve() != (ROOT / 'ComfyUI').resolve():
                continue
            if 'main.py' not in cmd or '--port' not in cmd or cmd[cmd.index('--port') + 1] != str(port):
                continue
            found.append(int(proc.name))
        except (OSError, ValueError, IndexError):
            pass
    return found


def stop_comfy():
    for port in PORTS:
        pids = comfy_pids(port)
        for pid in pids:
            try: os.kill(pid, signal.SIGTERM)
            except ProcessLookupError: pass
        deadline = time.monotonic() + 30
        while comfy_pids(port) and time.monotonic() < deadline:
            time.sleep(.5)
        for pid in set(comfy_pids(port)) & set(pids):
            try: os.kill(pid, signal.SIGKILL)
            except ProcessLookupError: pass
        deadline = time.monotonic() + 10
        while comfy_pids(port) and time.monotonic() < deadline:
            time.sleep(.5)
        if comfy_pids(port) or healthy(port):
            raise RuntimeError(f'Chưa dừng được ComfyUI :{port}; chưa bật Qwen để tránh tranh GPU.')
        (ROOT / 'logs' / ('comfy.pid' if port == 8188 else 'comfy_8189.pid')).unlink(missing_ok=True)


def restore_qwen():
    write(phase='restoring', message='Đang khởi động lại Qwen3.8 trên 2 GPU')
    service('start', (SERVICES[0],))
    wait_health(8000)
    write(message='Qwen3.8 đã sẵn sàng; đang khởi động Qwen3 Embedding')
    service('start', (SERVICES[1],))
    wait_health(8002)


def run(action, operation):
    with lock(RUN):
        with lock():
            if read().get('operation') != operation:
                return
        try:
            if action == 'start':
                write(message='Đang dừng Qwen3.8 và Qwen3 Embedding để nhường 2 GPU')
                service('stop')
                stop_comfy()  # restart existing instances to discard any old low/novram flags
                start_comfy()
                write(phase='video', message='ComfyUI 2 GPU sẵn sàng · mỗi GPU tạo một cảnh', error='')
            else:
                write(message='Đang dừng ComfyUI trên cả hai GPU')
                stop_comfy()
                restore_qwen()
                write(phase='off', message='Đã dừng ComfyUI · Qwen3.8 và Embedding đã sẵn sàng', error='')
        except Exception as e:
            error = str(e)
            print(f'Model transition failed: {error}', flush=True)
            if action == 'start':
                try:
                    write(message='Bật ComfyUI thất bại; đang khôi phục hai Qwen')
                    stop_comfy()
                    restore_qwen()
                    error += ' · Đã khôi phục hai Qwen.'
                except Exception as restore_error:
                    error += f' · Khôi phục chưa hoàn tất: {restore_error}'
            write(phase='error', message='Chuyển model chưa hoàn tất', error=error)


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
