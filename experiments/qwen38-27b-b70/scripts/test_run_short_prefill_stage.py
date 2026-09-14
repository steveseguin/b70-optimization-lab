import importlib.util
from pathlib import Path
import subprocess
import socket
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('stage', Path(__file__).with_name('run-short-prefill-stage.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class StageTests(unittest.TestCase):
    def test_kernel_faults_and_exact_benign_notice(self):
        self.assertEqual(m.faults('Sep13 xe 0000:03:00.0: Xe device coredump has been deleted.'), [])
        for text in ('xe 0000:03:00.0: GPU reset', 'drm] Timedout job', 'soft lockup', 'xe 0000:03:00.0: coredump saved'):
            self.assertEqual(m.faults(text), [text])

    def test_owned_client_group_terminated(self):
        proc = subprocess.Popen(['sleep', '60'], start_new_session=True)
        try:
            m.Stage.terminate(proc)
            self.assertIsNotNone(proc.poll())
        finally:
            if proc.poll() is None: proc.kill()

    def test_journal_failure_propagates(self):
        with patch.object(m.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'journalctl')):
            with self.assertRaises(subprocess.CalledProcessError):
                m.checked(['journalctl', '-k'])

    def test_active_listener_still_rejected(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', 0))
            listener.listen(1)
            with self.assertRaises(OSError):
                m.check_port_available(listener.getsockname()[1])

    def test_recent_closed_connection_port_reusable(self):
        with socket.socket() as listener:
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            listener.bind(('127.0.0.1', 0))
            port = listener.getsockname()[1]
            listener.listen(1)
            with socket.create_connection(('127.0.0.1', port), timeout=2) as client:
                accepted, _ = listener.accept()
                # Server closes first, leaving its port in TIME_WAIT after ACK.
                accepted.shutdown(socket.SHUT_WR)
                self.assertEqual(client.recv(1), b'')
                client.shutdown(socket.SHUT_WR)
                self.assertEqual(accepted.recv(1), b'')
                accepted.close()
        m.check_port_available(port)

    def test_profile_scope(self):
        self.assertEqual({k: v[2:4] for k, v in m.PROFILES.items()},
                         {'4b': (1,3), '9b': (1,3), '27b-int4': (2,4), '27b-fp8': (2,1)})

if __name__ == '__main__': unittest.main()
