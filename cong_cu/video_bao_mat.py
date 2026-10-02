"""Server integration. Key is provisioned explicitly, never regenerated on startup."""
import os
import hashlib
import tempfile
from contextlib import contextmanager
from pathlib import Path
from giai_ma_xvideo.xvideo import Reader, encrypt, decrypt, parse_key

GOC = Path(__file__).resolve().parent.parent
KEY_FILE = GOC / '.bao_mat' / 'video.key'


def key():
    p = Path(os.environ.get('XVIDEO_KEY_FILE', str(KEY_FILE)))
    return parse_key(p.read_text(encoding='ascii'))


def seal(source, dest):
    return encrypt(Path(source), Path(dest), key())


@contextmanager
def workspace():
    # Plaintext intermediates stay in a private RAM directory on this Linux server.
    with tempfile.TemporaryDirectory(prefix='xvideo-', dir='/dev/shm') as name:
        yield Path(name)


def unpack(source, dest):
    return decrypt(Path(source), Path(dest), key())


def merged_path(project: Path) -> Path:
    """Stable neutral filename; independent of project title."""
    code = hashlib.sha256(project.name.encode()).hexdigest()[:16]
    return project / f"bd_{code}.brd"
