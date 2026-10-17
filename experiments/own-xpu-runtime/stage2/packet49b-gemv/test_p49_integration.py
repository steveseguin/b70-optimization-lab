import json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
import window, storage
from types import SimpleNamespace

class IntegrationTests(unittest.TestCase):
    def test_direct_model_windows_wait_for_complete_oracle(self):
        with patch('shared_oracle.completed_binding',side_effect=ValueError('incomplete')) as status:
            for name in ('KD','W2m','WS','WSs','WS128','WS128x'):
                with self.assertRaises(ValueError):window.admit_oracle(SimpleNamespace(window=name))
            for name in ('K0','K1a','K1b','K2','W0p'):window.admit_oracle(SimpleNamespace(window=name))
            self.assertEqual(status.call_count,6)
        with patch('shared_oracle.completed_binding',return_value={'completion_sha256':'bound'}):
            window.admit_oracle(SimpleNamespace(window='W2m',oracle=window.P/'oracle/results/incident-retrospective'))
            window.admit_oracle(SimpleNamespace(window='WS128',suite_manifest=window.P/'oracle/results/suite-manifest.json'))
            with self.assertRaises(ValueError):window.admit_oracle(SimpleNamespace(window='W2m',oracle=Path('/wrong')))
            with self.assertRaises(ValueError):window.admit_oracle(SimpleNamespace(window='WS128',suite_manifest=Path('/wrong')))

    def test_fresh_three_owners(self):
        window.fresh_k1_owners({'pids':[1,2,3,4]},{'pids':[5,6,7,8]})
        for bad in ([5,6,7],[1,5,6,7],[5,5,6,7]):
            with self.assertRaises(ValueError):window.fresh_k1_owners({'pids':[1,2,3,4]},{'pids':bad})

    def test_external_path_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            base=Path(folder)
            with patch.object(window,'B',base):
                self.assertEqual(window.output_path(base/'new'),base/'new')
                with self.assertRaises(ValueError):window.output_path(base)
                with self.assertRaises(ValueError):window.output_path(base.parent/'outside')

    def test_memory_policy_unchanged(self):
        import memory_gate
        ledger=json.loads((window.P/'memory-plan.json').read_text())
        row=memory_gate.configuration(ledger,4096,1,23)
        self.assertEqual(memory_gate.arena_bytes(row['ranks'][1]),32122890400)
        with self.assertRaises(ValueError):memory_gate.configuration(ledger,32768,1,23)

    def test_qsa_gate_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'output.bin').write_bytes(b'fixture')
            digest=storage.digest(root/'output.bin')
            build={'p49_qsa_fixture_host_sha256':digest,'artifacts_sha256':{'device/p49-qsa-fixtures':'binary'}}
            row=dict(schema='packet49.qsa-fixtures.v1',passed=True,reference_exact=True,checks=88,
                     device_executed=True,card=0,output_sha256=digest,
                     teardown=dict(safe_to_exit=True,exit_code=0,live_bytes=0,in_flight=0))
            (root/'receipt.json').write_text(json.dumps(row))
            self.assertEqual(window.qsa_fixture_gate(root,build,0)['checks'],88)
            for key,value in [('checks',87),('device_executed',False),('card',1),('output_sha256','wrong')]:
                changed=dict(row);changed[key]=value;(root/'receipt.json').write_text(json.dumps(changed))
                with self.assertRaises(ValueError):window.qsa_fixture_gate(root,build,0)

    def test_expert_gate_and_negative_controls(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'output.bin').write_bytes(b'expert')
            digest=storage.digest(root/'output.bin')
            build={'p49b_expert_fixture_host_sha256':digest,'artifacts_sha256':{'device/p49b-expert-fixtures':'binary'}}
            row=dict(schema='packet49b.expert-fixtures.v1',passed=True,reference_exact=True,checks=48,
                     device_executed=True,card=0,output_sha256=digest,
                     teardown=dict(safe_to_exit=True,exit_code=0,live_bytes=0,in_flight=0))
            (root/'receipt.json').write_text(json.dumps(row))
            self.assertEqual(window.expert_fixture_gate(root,build,0)['checks'],48)
            for key,value in [('checks',47),('device_executed',False),('card',1),('output_sha256','wrong')]:
                changed=dict(row);changed[key]=value;(root/'receipt.json').write_text(json.dumps(changed))
                with self.assertRaises(ValueError):window.expert_fixture_gate(root,build,0)

    def test_fault_signatures(self):
        for line in ('Fault response','CAT error','engine0 reset','reset render engine','job timed out','device coredump'):
            self.assertRegex(line,window.FAULT)
        self.assertNotRegex('changed unrelated configuration',window.FAULT)

if __name__=='__main__':unittest.main()
