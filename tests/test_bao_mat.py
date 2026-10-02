import base64
import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / p) for p in ('giao_dien', 'cong_cu', 'cong_cu/giai_ma_xvideo')]
from fastapi.testclient import TestClient
from cryptography.exceptions import InvalidTag
import server
import bao_mat as auth
import video_bao_mat as vb
import xuong as xg
import giai_ma
from xvideo import CHUNK, OFFSET, Reader, encrypt, decrypt


class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key = os.urandom(32)
        self.keytext = base64.b64encode(self.key).decode()
        (self.root / 'video.key').write_text(self.keytext)
        salt = os.urandom(16)
        (self.root / 'admin.json').write_text(json.dumps({'username': 'admin', 'salt': salt.hex(),
                                                      'hash': auth.password_hash('test-secret', salt)}))
        self.patches = [patch.object(vb, 'KEY_FILE', self.root / 'video.key'),
                        patch.object(auth, 'PRIVATE', self.root), patch.object(xg, 'XUONG', self.root / 'xuong')]
        for p in self.patches:
            p.start()
        self.project = xg.XUONG / 'test123'
        self.project.mkdir(parents=True)
        self.data = os.urandom(CHUNK * 2 + 111)
        plain = self.root / 'input.mp4'
        plain.write_bytes(self.data)
        self.brd = encrypt(plain, vb.merged_path(self.project), self.key)
        (self.project / 'du_an.json').write_text(json.dumps({'id': 'test123', 'ten': 'Thử nghiệm', 'canh': []}))
        self.client = TestClient(server.app)

    def tearDown(self):
        self.client.close()
        for p in reversed(self.patches):
            p.stop()
        self.temp.cleanup()

    def login(self):
        response = self.client.post('/api/dang-nhap', json={'username': 'admin', 'password': 'test-secret'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn('HttpOnly', response.headers['set-cookie'])
        self.assertIn('SameSite=strict', response.headers['set-cookie'])

    def test_roundtrip_and_no_plain_header(self):
        self.assertNotEqual(self.brd.read_bytes()[:32], self.data[:32])
        dest = decrypt(self.brd, self.root / 'out.mp4', self.key)
        self.assertEqual(dest.read_bytes(), self.data)
        with self.assertRaises(FileExistsError):
            decrypt(self.brd, dest, self.key)
        self.assertEqual(dest.read_bytes(), self.data)

    def test_delete_removes_local_project_and_its_comfy_leftovers(self):
        self.login()
        leftovers, others = [], []
        comfy = self.root / 'ComfyUI'
        for folder in (comfy / 'output' / 'xuong', comfy / 'input'):
            folder.mkdir(parents=True)
            own = folder / 'test123_ab12_abcdef.png'
            own.write_bytes(b'leftover')
            leftovers.append(own)
            other = folder / 'test1234_ab12_abcdef.png'
            other.write_bytes(b'keep')
            others.append(other)
        for relative in ('clip/ab.brd', 'tieng/ab.wav', 'anh_mau.png', '.tam/frame.png'):
            p = self.project / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'project data')
        neighbor = xg.XUONG / 'test1234'
        neighbor.mkdir()
        (neighbor / 'keep.brd').write_bytes(b'keep')
        with patch.object(xg.DA, 'COMFY', comfy), patch.object(server.HD, 'doc', return_value={'cho': [], 'dang': {}}):
            response = self.client.delete('/api/xuong/test123')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(self.project.exists())
        self.assertTrue(all(not p.exists() for p in leftovers))
        self.assertTrue(all(p.read_bytes() == b'keep' for p in others))
        self.assertEqual((neighbor / 'keep.brd').read_bytes(), b'keep')

    def test_delete_refuses_queued_or_running_project(self):
        self.login()
        job = {'du_an': 'test123', 'loai': 'canh', 'canh': 'ab'}
        for queued, running in (([job], {}), ([], {'gpu0': job})):
            with self.subTest(queued=bool(queued)), \
                 patch.object(server.HD, 'doc', return_value={'cho': queued, 'dang': running}), \
                 patch.object(server.HD, 'dang_chay', return_value=running):
                response = self.client.delete('/api/xuong/test123')
                self.assertEqual(response.status_code, 409)
                self.assertTrue(self.brd.exists())

    def test_wrong_key_tamper_truncation(self):
        for change in ('wrong-key', 'header', 'payload', 'truncated', 'appended', 'reorder'):
            with self.subTest(change=change):
                raw = bytearray(self.brd.read_bytes())
                key = self.key
                if change == 'wrong-key': key = os.urandom(32)
                if change == 'header': raw[19] ^= 1
                if change == 'payload': raw[OFFSET + CHUNK + 42] ^= 1
                if change == 'truncated': raw = raw[:-1]
                if change == 'appended': raw += b'X'
                if change == 'reorder':
                    n = CHUNK + 16
                    raw[OFFSET:OFFSET+2*n] = raw[OFFSET+n:OFFSET+2*n] + raw[OFFSET:OFFSET+n]
                src = self.root / 'bad.brd';src.write_bytes(raw)
                target = self.root / 'bad.mp4'
                with self.assertRaises((ValueError, InvalidTag)):
                    decrypt(src, target, key)
                self.assertFalse(target.exists())
                self.assertFalse(list(self.root.glob('.xvideo-*.tmp')))

    def test_auth_all_paths_logout_and_csrf(self):
        for path in ('/', '/api/xuong', '/xuong/test123/video', '/xuong/test123/clip/ab',
                     '/xuong/test123/tai-ve', '/bao-mat/key', '/bao-mat/cong-cu', '/docs', '/openapi.json', '/tinh/xuong.html'):
            with self.subTest(path=path):
                r = self.client.get(path + '?ma=old-link', follow_redirects=False)
                self.assertIn(r.status_code, (303, 401))
        self.assertEqual(self.client.post('/api/dang-nhap', json={'username': 'admin', 'password': 'wrong'}).status_code, 401)
        self.login()
        self.assertEqual(self.client.get('/').status_code, 200)
        r = self.client.post('/api/dang-xuat', headers={'Origin': 'https://evil.example'})
        self.assertEqual(r.status_code, 403)
        cookie = self.client.cookies.get(auth.COOKIE)
        self.assertEqual(self.client.post('/api/dang-xuat').status_code, 200)
        self.client.cookies.set(auth.COOKIE, cookie)
        self.assertEqual(self.client.get('/xuong/test123/video').status_code, 401)

    def test_throttle(self):
        for _ in range(10):
            self.assertEqual(self.client.post('/api/dang-nhap', json={'username': 'admin', 'password': 'wrong'}).status_code, 401)
        self.assertEqual(self.client.post('/api/dang-nhap', json={'username': 'admin', 'password': 'test-secret'}).status_code, 429)

    def test_playback_range_head(self):
        self.login()
        path = '/xuong/test123/video'
        self.assertEqual(self.client.get(path).content, self.data)
        for value, start, end in [('bytes=0-99', 0, 100), ('bytes=1048560-1048599', CHUNK-16, CHUNK+24),
                                   ('bytes=-45', len(self.data)-45, len(self.data)), ('bytes=2097152-', 2*CHUNK, len(self.data)),
                                   ('bytes=0-999999999', 0, len(self.data))]:
            r = self.client.get(path, headers={'Range': value})
            self.assertEqual(r.status_code, 206)
            self.assertEqual(r.content, self.data[start:end])
            self.assertEqual(r.headers['content-range'], f'bytes {start}-{end-1}/{len(self.data)}')
            self.assertIn('no-store', r.headers['cache-control'])
        for value in ('bytes=999999999-', 'bytes=-0', 'bytes=8-2', 'bytes=0-1,5-6', 'bytes=-', 'garbage'):
            self.assertEqual(self.client.get(path, headers={'Range': value}).status_code, 416)
        head = self.client.head(path)
        self.assertEqual(head.status_code, 200)
        self.assertEqual(head.content, b'')
        self.assertEqual(int(head.headers['content-length']), len(self.data))

    def test_zip_and_offline_folder_decoder(self):
        self.login()
        response = self.client.get('/xuong/test123/tai-ve?tat_ca=true')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn('video', response.headers['content-disposition'].lower())
        data = response.content
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(set(z.namelist()), {self.brd.name})
            self.assertEqual(z.read(self.brd.name), self.brd.read_bytes())
            self.assertNotIn(self.keytext.encode(), data)
            self.assertEqual(z.comment, b'')
            self.assertTrue(all(n.endswith('.brd') and 'video' not in n.lower() for n in z.namelist()))
        archive = self.root / 'download.zip'; archive.write_bytes(data)
        self.assertEqual(giai_ma.run(archive, self.root / 'zip-out', self.keytext, lambda _: None), 1)
        self.assertEqual((self.root / 'zip-out' / self.brd.with_suffix('.mp4').name).read_bytes(), self.data)
        self.assertEqual(giai_ma.run(self.project, self.root / 'folder-out', self.keytext, lambda _: None), 1)
        self.assertEqual((self.root / 'folder-out' / self.brd.with_suffix('.mp4').name).read_bytes(), self.data)
        with zipfile.ZipFile(archive, 'w') as z: z.writestr('../escape.brd', b'bad')
        with self.assertRaises(ValueError): giai_ma.run(archive, self.root / 'unsafe', self.keytext)
        tool = self.client.get('/bao-mat/cong-cu')
        with zipfile.ZipFile(io.BytesIO(tool.content)) as z:
            self.assertIn('Giai_ma_BRD/giai_ma.py', z.namelist())
            self.assertFalse(any(n.endswith('.key') for n in z.namelist()))

    def test_real_ffmpeg_render_and_merge_integration(self):
        (self.project / 'clip').mkdir()
        scene = {'id': 'ab12', 'prompt': 'test scene', 'giay': 1, 'anh': 'khong', 'loi_doc': ''}
        project = {'id': 'test123', 'ten': 'test', 'canh': [scene], 'hieu_ung_phim': False}
        path = self.project / 'du_an.json';path.write_text(json.dumps(project))
        def fake_render(*args, **kwargs):
            output = args[4]
            self.assertTrue(str(output).startswith('/dev/shm/'))
            xg.LV.chay([xg.LV.FF, '-v', 'error', '-y', '-f', 'lavfi', '-i', 'color=c=blue:s=128x96:r=24:d=1',
                       '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(output)])
        with patch.object(xg.DA, 've_mot_clip', side_effect=fake_render), patch.object(xg, 'W', 128), patch.object(xg, 'H', 96):
            self.assertFalse(xg.tao_canh(path, 'ab12')['giu'])
            self.assertTrue(xg.tao_canh(path, 'ab12')['giu'])
            self.assertEqual(xg.trang_thai_canh(scene, project, self.project)['trang_thai'], 'xong')
            result = xg.merge(path)
            self.assertEqual(result.suffix, '.brd')
            plain = vb.unpack(result, self.root / 'merged.mp4')
            self.assertAlmostEqual(xg.LV.do_dai(plain), 1, delta=0.1)
            self.assertFalse(list(self.project.rglob('*.mp4')))
            self.assertTrue(server._xg_doc(self.project)['video_moi'])


if __name__ == '__main__': unittest.main()
