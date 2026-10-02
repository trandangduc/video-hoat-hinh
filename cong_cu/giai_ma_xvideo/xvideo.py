"""XVIDEO v1: authenticated 1 MiB chunks, per-file HKDF key, AES-256-GCM.

The header and chunk position are authenticated. No original filename or key is stored.
This module has no dependency on the web application and is shipped with the decoder.
"""
from __future__ import annotations
import base64
import hashlib
import os
import struct
import tempfile
from pathlib import Path
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b'BRDPK\x00\x00\x01'
CHUNK = 1024 * 1024
HEADER = struct.Struct('>8sIQ32s')
OFFSET = HEADER.size + 16


def parse_key(value: str) -> bytes:
    try:
        key = base64.b64decode(value.strip(), validate=True)
    except Exception as e:
        raise ValueError('Key không hợp lệ (cần key Base64 32 byte).') from e
    if len(key) != 32:
        raise ValueError('Key phải có đúng 32 byte.')
    return key


def _cipher(key, salt):
    return AESGCM(HKDF(algorithm=hashes.SHA256(), length=32, salt=salt,
                      info=b'XVIDEO-v1').derive(key))


class Reader:
    def __init__(self, path: Path, key: bytes):
        self.file = open(path, 'rb')
        try:
            self.header = self.file.read(HEADER.size)
            magic, self.chunk, self.size, salt = HEADER.unpack(self.header)
            if magic != MAGIC or self.chunk != CHUNK:
                raise ValueError('Không phải file XVIDEO v1 hợp lệ.')
            self.aes = _cipher(key, salt)
            self.aes.decrypt(bytes(12), self.file.read(16), self.header)
            count = (self.size + CHUNK - 1) // CHUNK
            if os.fstat(self.file.fileno()).st_size != OFFSET + self.size + 16 * count:
                raise ValueError('File bị cắt ngắn hoặc thay đổi kích thước.')
        except BaseException:
            self.close()
            raise

    def chunks(self, start=0, end=None):
        end = self.size if end is None else end  # exclusive
        if not 0 <= start <= end <= self.size:
            raise ValueError('Khoảng byte không hợp lệ.')
        if start == end:
            return
        for i in range(start // CHUNK, (end - 1) // CHUNK + 1):
            self.file.seek(OFFSET + i * (CHUNK + 16))
            n = min(CHUNK, self.size - i * CHUNK)
            nonce = (i + 1).to_bytes(12, 'big')
            plain = self.aes.decrypt(nonce, self.file.read(n + 16), self.header + nonce)
            yield plain[max(0, start - i * CHUNK):min(n, end - i * CHUNK)]

    def close(self):
        self.file.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def encrypt(source: Path, dest: Path, key: bytes):
    source, dest = Path(source), Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    before = source.stat()
    header = HEADER.pack(MAGIC, CHUNK, before.st_size, os.urandom(32))
    aes = _cipher(key, HEADER.unpack(header)[3])
    fd, name = tempfile.mkstemp(prefix='.' + dest.name, suffix='.tmp', dir=dest.parent)
    tmp = Path(name)
    try:
        digest = hashlib.sha256()
        with os.fdopen(fd, 'wb') as out, source.open('rb') as inp:
            out.write(header)
            out.write(aes.encrypt(bytes(12), b'', header))
            i = 1
            while block := inp.read(CHUNK):
                digest.update(block)
                nonce = i.to_bytes(12, 'big')
                out.write(aes.encrypt(nonce, block, header + nonce))
                i += 1
            out.flush()
            os.fsync(out.fileno())
        check = hashlib.sha256()
        with Reader(tmp, key) as reader:
            for block in reader.chunks():
                check.update(block)
        after = source.stat()
        if check.digest() != digest.digest() or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise ValueError('Nguồn thay đổi trong khi mã hóa; giữ nguyên nguồn.')
        os.utime(tmp, ns=(before.st_atime_ns, before.st_mtime_ns))
        os.replace(tmp, dest)
        # Persist the replacement before a migration may remove the original.
        if os.name == 'posix':
            dfd = os.open(dest.parent, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
    finally:
        tmp.unlink(missing_ok=True)
    return dest


def decrypt(source: Path, dest: Path, key: bytes):
    """Publish only after every authentication tag succeeds; never overwrite output."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.xvideo-', suffix='.tmp', dir=dest.parent)
    tmp = Path(name)
    try:
        with os.fdopen(fd, 'wb') as out, Reader(source, key) as reader:
            for block in reader.chunks():
                out.write(block)
            out.flush()
            os.fsync(out.fileno())
        os.link(tmp, dest)  # atomic and fails if destination already exists
    finally:
        tmp.unlink(missing_ok=True)
    return dest
