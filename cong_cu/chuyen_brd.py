"""Offline migration: stop workshop server/workers before running this tool."""
import argparse
import hashlib
import json
import os
import time
from pathlib import Path
import video_bao_mat as VB


def migrate(root: Path):
    key = VB.key()  # fail before touching any source if missing/invalid
    paths = sorted(root.rglob('*.mp4'))
    report = VB.GOC / 'logs' / 'chuyen_brd.jsonl'
    total = 0
    for i, source in enumerate(paths, 1):
        dest = VB.merged_path(source.parent) if source.name == 'video.mp4' else source.with_suffix('.brd')
        before = source.stat()
        VB.encrypt(source, dest, key)
        # Independent SHA-256 of original and decrypted persisted replacement before unlink.
        original, restored = hashlib.sha256(), hashlib.sha256()
        with source.open('rb') as inp:
            while block := inp.read(1024 * 1024): original.update(block)
        with VB.Reader(dest, key) as reader:
            for block in reader.chunks(): restored.update(block)
        after = source.stat()
        if original.digest() != restored.digest() or (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
            raise RuntimeError(f'Xác minh thất bại; giữ lại nguồn {source}')
        with report.open('a') as log:
            log.write(json.dumps({'source':str(source.relative_to(root)), 'dest':str(dest.relative_to(root)),
                                  'bytes':before.st_size,'sha256':original.hexdigest(),'verified':True,'at':time.time()})+'\n')
            log.flush();os.fsync(log.fileno())
        source.unlink()
        total += before.st_size
        if i % 20 == 0 or i == len(paths): print(f'{i}/{len(paths)} verified; {total / 1024**3:.2f} GiB', flush=True)
    for project in root.glob('*/du_an.json'):
        data = json.loads(project.read_text())
        legacy, dest = project.parent / 'video.brd', VB.merged_path(project.parent)
        if legacy.exists():
            if dest.exists():
                raise FileExistsError(f'Không ghi đè {dest}')
            legacy.rename(dest)
        if dest.exists() and data.get('video') != dest.name:
            data['video'] = dest.name
            tmp = project.with_suffix('.migrate.tmp')
            tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2));tmp.replace(project)
    print(f'Done. Remaining MP4: {len(list(root.rglob("*.mp4")))}', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    args = parser.parse_args()
    migrate(args.folder.resolve())
