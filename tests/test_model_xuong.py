import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock
sys.path[:0] = [str(Path(__file__).resolve().parents[1] / x) for x in ('cong_cu','giao_dien')]
import model_xuong as mx
import server
from fastapi.testclient import TestClient


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.patches = [patch.object(mx, name, self.root / name.lower()) for name in ('STATE','LOCK','USE','RUN')]
        for p in self.patches: p.start()
        mx.write(phase='off', error='')
    def tearDown(self):
        for p in self.patches: p.stop()
        self.temp.cleanup()
    def test_start_stops_only_two_services_before_comfy(self):
        events=[]
        mx.write(operation='test')
        with patch.object(mx,'stop_comfy',side_effect=lambda:events.append('stop-comfy')), patch.object(mx,'service',side_effect=lambda action,names=mx.SERVICES:events.append((action,names))), patch.object(mx,'start_comfy',side_effect=lambda:events.append('comfy')):
            mx.run('start','test')
        self.assertEqual(events,[('stop',mx.SERVICES),'stop-comfy','comfy'])
        self.assertEqual(mx.read()['phase'],'video')
    def test_stop_releases_comfy_before_restore(self):
        events=[]
        mx.write(operation='test',phase='video')
        with patch.object(mx,'stop_comfy',side_effect=lambda:events.append('stop-comfy')), patch.object(mx,'service',side_effect=lambda action,names:events.append((action,names))), patch.object(mx,'wait_health',side_effect=lambda port:events.append(port)):
            mx.run('stop','test')
        self.assertEqual(events,['stop-comfy',('start',(mx.SERVICES[0],)),8000,('start',(mx.SERVICES[1],)),8002])
        self.assertEqual(mx.read()['phase'],'off')
    def test_start_failure_rolls_back(self):
        mx.write(operation='test')
        with patch.object(mx,'service'),patch.object(mx,'start_comfy',side_effect=RuntimeError('GPU failed')),patch.object(mx,'stop_comfy') as stop,patch.object(mx,'restore_qwen') as restore:
            mx.run('start','test')
        self.assertEqual(stop.call_count,2);restore.assert_called_once()
        self.assertEqual(mx.read()['phase'],'error')
        self.assertIn('GPU failed',mx.read()['error'])
    def test_stop_failure_does_not_start_qwen_on_busy_gpu(self):
        mx.write(operation='test')
        with patch.object(mx,'stop_comfy',side_effect=RuntimeError('still alive')),patch.object(mx,'restore_qwen') as restore:
            mx.run('stop','test')
        restore.assert_not_called()
        self.assertEqual(mx.read()['phase'],'error')
    def test_busy_and_lease_reject_transition(self):
        with patch.object(mx.subprocess,'Popen') as process:
            with self.assertRaises(RuntimeError):mx.request('stop',lambda:True)
            mx.write(phase='video')
            with mx.lease():
                with self.assertRaises(RuntimeError):mx.request('stop')
            process.assert_not_called()
        mx.write(phase='off')
        with self.assertRaises(RuntimeError):
            with mx.lease():pass
    def test_double_click_and_invalid_action(self):
        mx.write(phase='starting')
        with patch.object(mx,'transition_alive',return_value=True),patch.object(mx.subprocess,'Popen') as process:
            with self.assertRaises(RuntimeError):mx.request('start')
            with self.assertRaises(ValueError):mx.request('restart-arbitrary-service')
            process.assert_not_called()
    def test_status_needs_both_gpus_and_no_qwen(self):
        mx.write(phase='video')
        with patch.object(mx,'healthy',side_effect=lambda port,path:port in mx.PORTS):
            self.assertTrue(mx.status()['ready'])
        with patch.object(mx,'healthy',side_effect=lambda port,path:port==8188):
            self.assertFalse(mx.status()['ready'])
        with patch.object(mx,'healthy',return_value=True):
            self.assertFalse(mx.status()['ready'])
        mx.write(phase='starting')
        with patch.object(mx,'healthy',return_value=False),patch.object(mx,'transition_alive',return_value=False):
            self.assertEqual(mx.status()['phase'],'error')
    def test_old_boot_cannot_resume_video_jobs(self):
        mx.write(phase='video')
        data=mx.read();data['boot']='previous-boot';mx.STATE.write_text(json.dumps(data))
        self.assertFalse(mx.allowed())
        with self.assertRaises(RuntimeError):
            with mx.lease():pass
        with patch.object(mx,'healthy',return_value=False):
            self.assertEqual(mx.status()['phase'],'error')

    def test_gpu_pinning_and_fast_flags_unchanged(self):
        with patch.object(mx.subprocess,'run') as run,patch.object(mx,'healthy',return_value=True):
            mx.start_comfy()
        self.assertEqual(run.call_count,2)
        self.assertEqual([c.kwargs['env']['CUDA_VISIBLE_DEVICES'] for c in run.call_args_list],['0','1'])
        self.assertEqual([c.kwargs['env']['COMFY_PORT'] for c in run.call_args_list],['8188','8189'])
        for c in run.call_args_list:self.assertNotIn('VRAM',c.kwargs['env'])
    def test_endpoints_require_login_and_disabled_mode_blocks_jobs(self):
        client=TestClient(server.app)
        with patch.object(server.AUTH,'session_valid',return_value=False):
            self.assertEqual(client.get('/api/xuong-model').status_code,401)
            self.assertEqual(client.post('/api/xuong-model/start').status_code,401)
            self.assertEqual(client.post('/api/xuong/test123/tao-het').status_code,401)
        with patch.object(server.AUTH,'session_valid',return_value=True):
            self.assertEqual(client.post('/api/xuong/test123/tao-het').status_code,409)
            self.assertEqual(client.post('/api/xuong-model/arbitrary').status_code,400)
            mx.write(phase='video')
            with patch.object(mx,'status',return_value={'ready':False}):
                self.assertEqual(client.post('/api/xuong/test123/tao-het').status_code,409)
            with patch.object(mx,'status',return_value={'ready':True}):
                self.assertEqual(client.post('/api/xuong/test123/tao-het').status_code,404)
            with patch.object(server,'_model_busy',return_value=True):
                self.assertEqual(client.post('/api/xuong-model/stop').status_code,409)
        client.close()

if __name__=='__main__':unittest.main()
