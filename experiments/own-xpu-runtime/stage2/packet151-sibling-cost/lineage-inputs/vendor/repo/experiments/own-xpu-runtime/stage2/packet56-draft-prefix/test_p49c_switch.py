"""Exercise unchanged p49b STOP behavior with CPU-only mocked launches."""
import fcntl
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import queue_runner as new_queue
import storage

OLD=Path(__file__).resolve().parent.parent/'packet49b-gemv/queue_runner.py'
spec=importlib.util.spec_from_file_location('p49b_queue_switch_audit',OLD)
old=importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)

class SwitchTests(unittest.TestCase):
    def test_failed_precheck_never_creates_chain_or_launches(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'new-chain'
            args=SimpleNamespace(authorized_device_window=True,output_root=out,phase='early',wait_oracle=False)
            with patch.object(new_queue.os,'getpriority',return_value=0),patch.object(new_queue.os,'sched_getaffinity',return_value=new_queue.DEVICE_CORES),patch.object(new_queue,'user_unit_gate'),patch.object(new_queue,'admitted_output',return_value=out),patch.object(storage,'precheck',return_value={'passed':False,'margin_bytes':-1}),patch.object(new_queue.subprocess,'Popen') as launch:
                with self.assertRaisesRegex((RuntimeError,ValueError),'storage'):
                    new_queue.run(args)
                launch.assert_not_called()
            self.assertFalse(out.exists())

    def test_predecessor_chain_existence_does_not_affect_admission(self):
        # Read-only observation of the real immutable queued chain; no lookup
        # of it belongs to the new queue's output-path admission.
        predecessor=Path('/home/steve/own-xpu-runtime-results/packet49b-gemv/build/device-cards01-a')
        self.assertTrue(predecessor.is_dir())
        chain=Path('/home/steve/own-xpu-runtime-results/packet49c-round2/build/device-cards01-a')
        self.assertEqual(new_queue.admitted_output(chain),chain)
        with self.assertRaises(ValueError):new_queue.admitted_output(chain.with_name('device-cards01-b'))

    def exercise(self,ready=False):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'p49b';out.mkdir()
            state={'last_stop':0,'gap':0,'completed':list(old.EARLY)}
            (out/'queue-state.json').write_text(json.dumps(state))
            def stop_after_wait(seconds):
                self.assertEqual(seconds,5)
                (out/'STOP').write_text('coordinator switch to p49c\n')
            def oracle():
                if ready:(out/'STOP').write_text('coordinator switch\n')
                return ready
            args=SimpleNamespace(authorized_device_window=True,output_root=out,phase='model',wait_oracle=True)
            with patch.object(old.os,'getpriority',return_value=0),patch.object(old.os,'sched_getaffinity',return_value=old.DEVICE_CORES),patch.object(old,'user_unit_gate'),patch.object(old,'admitted_output',return_value=out),patch.object(old,'journal',return_value='mock'),patch.object(old,'oracle_ready',side_effect=oracle),patch.object(old.time,'sleep',side_effect=stop_after_wait),patch.object(old.subprocess,'Popen') as launch:
                with self.assertRaisesRegex(RuntimeError,'STOP before launch' if ready else 'STOP while awaiting'):
                    old.run(args)
                launch.assert_not_called()
            self.assertFalse((out/'KD').exists())
            self.assertFalse((out/'running.json').exists())
            self.assertEqual(json.loads((out/'queue-state.json').read_text()),state)
            names={'queue.lock','queue-state.json','STOP'}
            if not ready:names.add('waiting.json')
            self.assertEqual({p.name for p in out.iterdir()},names)
            with (out/'queue.lock').open('a') as handle:
                fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            chain=Path('/home/steve/own-xpu-runtime-results/packet49c-round2/build/device-cards01-a')
            self.assertEqual(new_queue.admitted_output(chain),chain)

    def test_stop_while_waiting_releases_only_chain_lock_without_launch(self):
        self.exercise()

    def test_stop_wins_when_oracle_turns_ready(self):
        self.exercise(ready=True)

if __name__=='__main__':unittest.main()
