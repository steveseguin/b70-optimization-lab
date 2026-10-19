import copy,json,unittest
from pathlib import Path
import composition as C
import memory_plan as M
import window as W
P=Path(__file__).resolve().parent
class ResidentTests(unittest.TestCase):
    def test_exact_production_lookup_identity_and_corruption(self):
        row=dict(lookup_residency=json.loads((P/'lineage/synthetic-lookup-receipt.json').read_text()))
        self.assertEqual(C.check_lookups(row),29321610240)
        mutations=[lambda r:r['lookup_residency'].update(enabled=False),
                   lambda r:r['lookup_residency']['tensors'].pop(),
                   lambda r:r['lookup_residency']['tensors'][0].update(bytes=521471999),
                   lambda r:r['lookup_residency']['tensors'][0].update(resident_sha256='b'*64)]
        for mutate in mutations:
            bad=copy.deepcopy(row);mutate(bad)
            with self.assertRaises(ValueError):C.check_lookups(bad)
    def test_complete_copy_allocation_charged_once_at_every_stage(self):
        for window in ('KD','W2m','WS','WS128x','WS128','WSCREEN'):
            b=M.window_plan(window);h=b['host_categories'];pins=h['pinned_packed_experts']
            self.assertEqual(h['resident_lookup_bytes'],29321610240)
            self.assertEqual(h['file_backed_nonexpert_and_lookup_bound'],4001477120)
            self.assertEqual(b['device_categories']['expert_cache_arena'],21552729600)
            self.assertEqual(b['host_bound_bytes'],90400317440)
            self.assertEqual(b['host_required_available_bytes'],98990252032)
            for copied in (0,521472000,29321610240):
                sample=W.account_memory({'anonymous_bytes':copied},dict(MemAvailable=M.HOST_RESERVE,GPUActive=pins),0,pins,b)
                self.assertEqual(sample['host_accounted_bytes'],pins+copied+4001477120)
    def test_planned_writes_within_measured_limit(self):
        row=json.loads((P/'payload-sizes.json').read_text())
        for record in row['records'].values():
            self.assertGreater(record['measured_bytes'],0)
            self.assertLessEqual(record['planned_writes'],3*record['measured_bytes'])
if __name__=='__main__':unittest.main()
