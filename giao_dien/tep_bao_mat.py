"""Authenticated range playback and encrypted ZIP downloads."""
import re
import tempfile
import zipfile
from pathlib import Path
from urllib.parse import quote
from fastapi import HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from starlette.background import BackgroundTask
import video_bao_mat as VB


def playback(path: Path, req: Request):
    if not path.is_file():
        raise HTTPException(404, 'Không có tệp.')
    reader = VB.Reader(path, VB.key())
    size, start, end, status = reader.size, 0, reader.size, 200
    headers = {'Accept-Ranges': 'bytes', 'Cache-Control': 'no-store, private'}
    byte_range = req.headers.get('range')
    if byte_range:
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', byte_range)
        try:
            if not match or not any(match.groups()) or size == 0:
                raise ValueError()
            left, right = match.groups()
            if left:
                start = int(left)
                end = min(size, int(right) + 1) if right else size
            else:
                suffix = int(right)
                if suffix <= 0:
                    raise ValueError()
                start = max(0, size - suffix)
            if start >= end or start >= size:
                raise ValueError()
        except ValueError:
            reader.close()
            return Response(status_code=416, headers={**headers, 'Content-Range': f'bytes */{size}'})
        status = 206
        headers['Content-Range'] = f'bytes {start}-{end - 1}/{size}'
    headers['Content-Length'] = str(end - start)
    if req.method == 'HEAD':
        reader.close()
        return Response(status_code=status, headers=headers, media_type='video/mp4')
    iterator = reader.chunks(start, end)
    # Validate the first requested chunk before response headers are committed.
    try:
        first = next(iterator, b'')
    except BaseException:
        reader.close()
        raise
    def stream():
        try:
            if first:
                yield first
            yield from iterator
        finally:
            reader.close()
    return StreamingResponse(stream(), status_code=status, headers=headers, media_type='video/mp4',
                             background=BackgroundTask(reader.close))


def zip_response(files, filename):
    # Only encrypted payloads or decoder source enter this temporary archive.
    tmp = tempfile.TemporaryFile()
    try:
        with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
            for source, name in files:
                z.write(source, arcname=name)
        length = tmp.tell()
        tmp.seek(0)
    except BaseException:
        tmp.close()
        raise
    def stream():
        try:
            while block := tmp.read(1024 * 1024):
                yield block
        finally:
            tmp.close()
    return StreamingResponse(stream(), media_type='application/zip', headers={
        'Content-Length': str(length), 'Content-Disposition': "attachment; filename*=UTF-8''" + quote(filename),
        'Cache-Control': 'no-store, private'}, background=BackgroundTask(tmp.close))
