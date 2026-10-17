"""Placement binding, real lineage admission, and pre-device refusal checks."""
import copy
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import common as C
import placement as P
import screen
import tp2_worker
import ab


class PlacementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = C.P56.parent / 'packet61x-spin-hcfusion-wait'
        cls.args = SimpleNamespace(lineage=cls.root, profile='tp2', binary=None,
            dispatch=None, seal=cls.root/'screen-seal.json', timing='token', placement='1-split23')
        cls.control = C.sealed(cls.args)
        cls.seal = C.read(cls.args.seal)

    def identity(self, name):
        result = copy.deepcopy(self.control)
        result['placement'] = P.admit(self.root, self.seal, self.args.seal,
                                      Path(result['dispatch']), name)
        return result

    def test_four_memory_admissions_and_two_engine_refusals(self):
        for name, layers in [('1-split23',[23,25]),('0-split23',[23,25]),('0',[22,26]),('1',[24,24])]:
            with self.subTest(placement=name):
                p = self.identity(name)['placement']
                self.assertTrue(p['memory_admitted'])
                self.assertEqual(p['target_layers'], layers)
                self.assertEqual(p['supported'], name in ('1-split23','1'))
                self.assertEqual(p['rank_dispatch_sha256'], [self.control['dispatch_sha256']]*2)
                if not p['supported']:self.assertIn('resident output.weight', p['reason'])

    def test_identity_tamper_and_unsupported_refuse_before_adapter(self):
        for name in ('0','0-split23'):
            with tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp)/'must-not-exist'
                with patch.object(screen.subprocess, 'Popen', side_effect=AssertionError('device launch')):
                    with self.assertRaisesRegex(ValueError, 'Unsupported'):
                        tp2_worker.run(self.identity(name), output, 3600)
                self.assertFalse(output.exists())
        identity = self.identity('1')
        identity['placement']['draft_rank'] = 0
        with self.assertRaisesRegex(ValueError, 'identity/placement changed'):
            P.verify_identity(identity)
        identity = self.identity('1')
        identity['placement']['target_split'] = 23
        with self.assertRaisesRegex(ValueError, 'identity/placement changed'):
            P.verify_identity(identity)

    def test_memory_margin_and_rank_ownership_fail_closed(self):
        original = P.read
        for kind in ('reserve', 'owner'):
            ledger = original(self.root/'memory-plan.json')
            if kind == 'reserve':
                ledger['placements']['1']['capacities']['4096']['ranks'][0]['allocation_margin_passed'] = False
            else:ledger['placements']['1']['layer_boundary'] = 23
            def reader(path):
                return ledger if Path(path) == self.root/'memory-plan.json' else original(path)
            with patch.object(P, 'read', side_effect=reader):
                with self.assertRaises(ValueError):self.identity('1')

    def test_plans_have_no_device_or_run_directory_including_unsupported(self):
        for name in P.PLACEMENTS:
            out = C.HERE/'evidence'/('placement-cpu-test-'+name)
            argv=['--lane','B','--lineage',str(self.root),'--seal',str(self.args.seal),
                  '--placement',name,'--output',str(out),'--plan']
            with patch.object(screen.subprocess,'Popen',side_effect=AssertionError('launch')), \
                 patch.object(C.S,'journal',side_effect=AssertionError('journal')), \
                 patch.object(screen,'topology_admit',side_effect=AssertionError('discovery')), \
                 patch('sys.stdout',new=io.StringIO()) as stdout:
                self.assertEqual(screen.main(argv), 2 if name.startswith('0') else 0)
                result=json.loads(stdout.getvalue())
            self.assertFalse(result['device_executed'])
            self.assertEqual(result['identity']['placement']['name'],name)
            self.assertFalse(out.exists())

    def test_ab_propagates_placement(self):
        identity = dict(self.identity('1'),lane='B')
        cmd=ab.lane_command(identity,'B',Path('/out'),Path('/review'),Path('/pair'))
        self.assertEqual(cmd[cmd.index('--placement')+1], '1')

    def test_unknown_name_and_changed_audit_refuse(self):
        with self.assertRaisesRegex(ValueError, 'unknown placement'):self.identity('arbitrary')
        original=P.read
        policy=original(C.HERE/'placements.json')
        policy['seal_sha256']='0'*64
        with patch.object(P,'read',side_effect=lambda path: policy if Path(path)==C.HERE/'placements.json' else original(path)):
            with self.assertRaisesRegex(ValueError,'another lineage seal'):self.identity('1')


if __name__ == '__main__':unittest.main()
