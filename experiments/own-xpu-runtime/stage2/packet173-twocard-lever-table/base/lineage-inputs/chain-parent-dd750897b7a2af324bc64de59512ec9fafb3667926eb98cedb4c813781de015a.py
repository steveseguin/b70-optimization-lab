"""CPU-only admission regressions; no binary, device discovery or model read."""
import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import memory_gate,memory_plan,window

P=Path(__file__).resolve().parent
CAP=30*1024**3
SAVING=248*1024**2

def retotal(ledger,row,owned):
    row['target_modeled_allocations_bytes']=owned-row['draft_total_bytes']-row['draft_duplicate_head_bytes']
    row['target_total_bytes']=row['target_modeled_allocations_bytes']+row['allocation_reserve_bytes']
    row['total_with_mtp_bytes']=owned+row['allocation_reserve_bytes']
    row['free_with_mtp_bytes']=ledger['capacity_bytes']-row['total_with_mtp_bytes']
    row['allocation_margin_passed']=row['free_with_mtp_bytes']>=ledger['minimum_free_bytes']

class ArenaAdmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ledger=memory_plan.plan()

    def row(self,ledger=None,context=4096,rank=1):
        return (ledger or self.ledger)['placements']['1-split23']['capacities'][str(context)]['ranks'][rank]

    def legacy(self):
        old=copy.deepcopy(self.ledger)
        for r in self.row(old,rank=0),self.row(old,rank=1):
            retotal(old,r,memory_gate.arena_bytes(r)+SAVING*(2 if r['rank']==0 else 1))
        return old

    def test_incident_reproduced_before_device(self):
        old=self.legacy();r=self.row(old)
        self.assertEqual(memory_gate.arena_bytes(r),29_028_573_034+3_354_364_214)
        self.assertEqual(memory_gate.arena_bytes(r)-CAP,170_682_528)
        self.assertEqual(r['free_with_mtp_bytes']-old['minimum_free_bytes'],358_131_808)
        with self.assertRaisesRegex(ValueError,'30 GiB arena.*170682528'):
            memory_gate.configuration(old,4096,1,23)

    def test_new_exact_accounting(self):
        row=memory_gate.configuration(self.ledger,4096,1,23)
        self.assertEqual([memory_gate.arena_bytes(r) for r in row['ranks']],
                         [26_039_514_280,32_122_890_400])
        self.assertEqual([CAP-memory_gate.arena_bytes(r) for r in row['ranks']],
                         [6_172_740_440,89_364_320])
        self.assertEqual(self.row()['free_with_mtp_bytes'],2_118_178_656)

    def test_legacy_ledger_without_summary_still_refused(self):
        old=self.legacy();old.pop('arena_limit_bytes')
        for r in self.row(old,rank=0),self.row(old):
            for k in list(r):
                if k.startswith('arena_'):del r[k]
        with self.assertRaisesRegex(ValueError,'30 GiB arena'):
            memory_gate.configuration(old,4096,1,23)

    def test_boolean_or_summary_cannot_override_arena(self):
        old=self.legacy();r=self.row(old)
        r.update(arena_margin_passed=True,arena_device_bytes=1,arena_headroom_bytes=CAP,allocation_margin_passed=True)
        with self.assertRaisesRegex(ValueError,'30 GiB arena'):
            memory_gate.configuration(old,4096,1,23)

    def test_cap_cannot_be_raised(self):
        old=self.legacy();old['arena_limit_bytes']=32*1024**3
        with self.assertRaisesRegex(ValueError,'cap changed'):
            memory_gate.configuration(old,4096,1,23)

    def test_inconsistent_components_rejected(self):
        for key in ('target_total_bytes','total_with_mtp_bytes','target_modeled_allocations_bytes','allocation_reserve_bytes'):
            bad=copy.deepcopy(self.ledger);self.row(bad)[key]+=1
            with self.assertRaisesRegex(ValueError,'components'):
                memory_gate.configuration(bad,4096,1,23)

    def test_exact_arena_boundary_and_one_byte_over(self):
        for extra in (0,1):
            bad=copy.deepcopy(self.ledger);retotal(bad,self.row(bad),CAP+extra)
            if extra:
                with self.assertRaisesRegex(ValueError,'1 bytes over'):memory_gate.configuration(bad,4096,1,23)
            else:memory_gate.configuration(bad,4096,1,23)

    def test_default_configuration_also_checked(self):
        bad=copy.deepcopy(self.ledger);r=bad['placements']['1']['capacities']['4096']['ranks'][1]
        retotal(bad,r,CAP+1)
        with self.assertRaisesRegex(ValueError,'30 GiB arena'):memory_gate.configuration(bad,4096,1,0)

    def test_card_reserve_still_checked(self):
        bad=copy.deepcopy(self.ledger);bad['capacity_bytes']-=700_000_000
        for r in self.row(bad,rank=0),self.row(bad):retotal(bad,r,memory_gate.arena_bytes(r))
        with self.assertRaisesRegex(ValueError,'1.5 GB'):memory_gate.configuration(bad,4096,1,23)

    def test_32k_refused_even_if_scratch_saving_is_extended(self):
        bad=copy.deepcopy(self.ledger)
        for r in self.row(bad,32768,0),self.row(bad,32768,1):
            retotal(bad,r,memory_gate.arena_bytes(r)-SAVING*(2 if r['rank']==0 else 1))
        self.assertEqual(memory_gate.arena_bytes(self.row(bad,32768))-CAP,453_798_048)
        self.assertGreater(self.row(bad,32768)['free_with_mtp_bytes'],1_500_000_000)
        with self.assertRaisesRegex(ValueError,'30 GiB arena'):memory_gate.configuration(bad,32768,1,23)

    def test_all_previously_valid_configurations(self):
        for c in (4096,32768):
            for dr,split in ((0,0),(1,0),(0,23)):
                memory_gate.configuration(self.ledger,c,dr,split)
        memory_gate.configuration(self.ledger,4096,0,24)
        with self.assertRaises(ValueError):memory_gate.configuration(self.ledger,32768,0,24)
        with self.assertRaises(ValueError):memory_gate.configuration(self.ledger,32768,1,23)

    def test_pinned_staging_is_not_device_arena(self):
        n=memory_gate.arena_bytes(self.row())
        census=dict(totals=dict(device=n),allocations=[dict(bytes=n,live=True,memory='device'),
            dict(bytes=4_214_796,live=True,memory='pinned'),dict(bytes=99,live=False,memory='device')])
        result=memory_gate.check(census,self.ledger,1,True,4096,1,23)
        self.assertEqual(result['arena_headroom_bytes'],89_364_320)

    def test_live_census_guard(self):
        n=CAP+1;census=dict(totals=dict(device=n),allocations=[dict(bytes=n,live=True,memory='device')])
        with self.assertRaisesRegex(ValueError,'live rank exceeds 30 GiB'):
            memory_gate.check(census,self.ledger,1,True,4096,1,23)

    def test_every_window_refuses_before_output_environment_or_children(self):
        original=Path.read_text
        legacy=json.dumps(self.legacy())
        def read(path,*args,**kw):
            return legacy if path==window.P/'memory-plan.json' else original(path,*args,**kw)
        with tempfile.TemporaryDirectory(prefix='speed6-admission-') as d:
            for name,diagnostic in ((name,d) for name in window.CONFIG for d in (False,True)):
                out=Path(d)/(name+str(diagnostic))
                argv=['window.py','--authorized-device-window','--window',name,'--card','2','--context','4096',
                      '--draft-rank','1','--target-split','23','--output',str(out)]
                if diagnostic:argv.append('--diagnostic-unsealed')
                with patch('sys.argv',argv),patch.object(Path,'read_text',read),patch.object(window,'environment_gate',side_effect=AssertionError('device environment reached')):
                    with self.assertRaisesRegex(ValueError,'30 GiB arena'):window.main()
                self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
