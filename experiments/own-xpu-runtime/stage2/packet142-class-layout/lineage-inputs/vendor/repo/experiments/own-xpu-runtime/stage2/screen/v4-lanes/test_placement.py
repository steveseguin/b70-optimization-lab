"""All packet64 choices are immutable, placement-bound and pre-device checked."""
import copy
import io
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import common as C
import placement as P
import screen
import ab

class PlacementTests(unittest.TestCase):
    def args(self, placement='1', kernel='production-control'):
        root=C.P56.parent/'packet64-record-bundle/selections'/(placement+'-'+kernel)
        return SimpleNamespace(lineage=root,profile='tp2',binary=None,dispatch=None,
                               seal=root/'screen-seal.json',timing='token',placement=placement)
    def test_all_choices_and_both_lanes_plan_without_device(self):
        for placement in ('1','1-split23'):
            for kernel in ('production-control','production-batch','draft-hc-control','draft-hc-batch'):
                args=self.args(placement,kernel)
                for lane in ('A','B'):
                    out=C.HERE/'evidence'/('cpu-'+placement+'-'+kernel+'-'+lane)
                    argv=['--lane',lane,'--lineage',str(args.lineage),'--seal',str(args.seal),'--placement',placement,'--output',str(out),'--plan']
                    with patch.object(screen.subprocess,'Popen',side_effect=AssertionError('launch')),patch.object(C.S,'journal',side_effect=AssertionError('journal')),patch.object(screen,'topology_admit',side_effect=AssertionError('discovery')),patch('sys.stdout',new=io.StringIO()) as stdout:
                        self.assertEqual(screen.main(argv),0)
                        row=json.loads(stdout.getvalue())
                    self.assertFalse(row['device_executed']);self.assertFalse(out.exists())
                    self.assertEqual(row['identity']['placement']['target_layers'],[24,24] if placement=='1' else [23,25])
    def test_wrong_placement_and_rank_zero_refuse(self):
        args=self.args()
        for placement in ('1-split23','0','0-split23'):
            args.placement=placement
            with self.assertRaisesRegex(ValueError,'placement differs'):C.sealed(args)
    def test_identity_tamper_refuses(self):
        identity=C.sealed(self.args())
        for field,value in (('draft_rank',0),('target_split',23)):
            changed=copy.deepcopy(identity);changed['placement'][field]=value
            with self.assertRaisesRegex(ValueError,'identity/placement changed'):P.verify_identity(changed)
    def test_memory_margin_and_rank_ownership_fail_closed(self):
        args=self.args();original=P.read
        for kind in ('reserve','owner'):
            ledger=original(args.lineage/'memory-plan.json')
            if kind=='reserve':ledger['placements']['1']['capacities']['4096']['ranks'][0]['allocation_margin_passed']=False
            else:ledger['placements']['1']['layer_boundary']=23
            with patch.object(P,'read',side_effect=lambda path:ledger if Path(path)==args.lineage/'memory-plan.json' else original(path)):
                with self.assertRaises(ValueError):C.sealed(args)
    def test_changed_audit_refuses(self):
        args=self.args();original=P.read
        row=original(args.lineage/'placement-audit.json');row['binary_sha256']='0'*64
        with patch.object(P,'read',side_effect=lambda path:row if Path(path)==args.lineage/'placement-audit.json' else original(path)):
            with self.assertRaisesRegex(ValueError,'binary changed'):C.sealed(args)
    def test_ab_propagates_placement(self):
        identity=dict(C.sealed(self.args()),lane='B')
        cmd=ab.lane_command(identity,'B',Path('/out'),Path('/review'),Path('/pair'))
        self.assertEqual(cmd[cmd.index('--placement')+1],'1')
if __name__=='__main__':unittest.main()
