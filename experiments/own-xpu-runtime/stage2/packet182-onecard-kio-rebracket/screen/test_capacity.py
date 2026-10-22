import json,tempfile,unittest
from pathlib import Path
import device_memory as D
import memory_plan as M
import views as V


class Capacity(unittest.TestCase):
    def test_maximum_retains_every_allowance(self):
        p=M.window_plan('WSCREEN')
        self.assertEqual(sum(p['device_categories'].values()),p['device_owned_bound_bytes'])
        self.assertEqual(p['device_categories']['expert_cache_arena'],V.MAX_BYTES)
        self.assertGreaterEqual(p['device_margin_bytes'],0)
        self.assertLess(p['device_margin_bytes'],256)
        self.assertEqual(p['device_categories']['workspace_bound']+p['device_categories']['exact_half_decode_table'],1024**3)
        self.assertEqual(p['device_categories']['control_transaction_bound'],1024**3)
        self.assertEqual(p['device_categories']['transfer_bound'],256*1024**2)
        self.assertEqual(p['device_categories']['target_4k_bf16_kv_index'],116391936)

    def test_admission_boundary(self):
        p=M.plan();required=p['host_required_available_bytes']
        self.assertTrue(M.admit({'MemAvailable':required},p)['passed'])
        with self.assertRaises(ValueError):M.admit({'MemAvailable':required-1},p)
        self.assertEqual(M.window_plan('K1')['host_required_available_bytes'],12*1024**3)

    def test_fixed_maintenance_and_capacity_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'views.tsv'
            for mode in ('serial','overlap'):
                V.write_table(p,'resident',mode)
                rows=[line.split() for line in p.read_text().splitlines()]
                self.assertEqual([r[3] for r in rows],[mode]*5)
                self.assertEqual([r[5] for r in rows],['mapped','resident','mapped','resident','mapped'])
            with self.assertRaises(ValueError):V.write_table(p,'resident','unknown')

    def test_smoke_and_every_v5_view_default_to_overlap(self):
        self.assertEqual(V.DEFAULT_MAINTENANCE,'overlap')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'views.tsv'
            for candidate in ('smoke','resident'):
                V.write_table(p,candidate)
                rows=[line.split() for line in p.read_text().splitlines()]
                self.assertEqual([r[3] for r in rows],['overlap']*len(V.bracket(candidate)))
                self.assertEqual([r[5] for r in rows],[v for _,v in V.bracket(candidate)])

    def test_measured_live_accounting_bounds(self):
        import window as W
        p=M.plan();host=p['host_categories'];pinned=host['pinned_packed_experts']
        shadow=host['gpuactive_shadow_bound'];file=host['file_backed_nonexpert_and_lookup_bound']
        anon=p['host_bound_bytes']-pinned-shadow-file
        snapshot={'MemAvailable':M.HOST_RESERVE,'GPUActive':pinned+shadow}
        row=W.account_memory({'anonymous_bytes':anon},snapshot,0,pinned,p)
        self.assertEqual(row['host_accounted_bytes'],p['host_bound_bytes'])
        with self.assertRaisesRegex(ValueError,'combined host memory'):
            W.account_memory({'anonymous_bytes':anon+1},snapshot,0,pinned,p)
        with self.assertRaisesRegex(ValueError,'shadow exceeds'):
            W.account_memory({'anonymous_bytes':0},dict(snapshot,GPUActive=pinned+shadow+1),0,pinned,p)

    def test_drm_duplicate_fd_and_reserve(self):
        with tempfile.TemporaryDirectory() as d:
            proc=Path(d);fd=proc/'7/fdinfo';fd.mkdir(parents=True)
            template='drm-driver: xe\ndrm-pdev: 0000:03:00.0\ndrm-client-id: 9\ndrm-total-vram0: {} KiB\n'
            for n in ('1','2'):(fd/n).write_text(template.format(29_000_000))
            row=D.observe([{'pid':7}],proc)
            self.assertEqual(row['clients'],1);self.assertEqual(row['bytes'],29_000_000*1024)
            self.assertTrue(row['passed'])
            (fd/'2').write_text(template.format(30_000_000))
            self.assertFalse(D.observe([{'pid':7}],proc)['passed'])
            (fd/'2').write_text(template.replace('KiB','GB').format(1))
            with self.assertRaises(ValueError):D.observe([{'pid':7}],proc)

if __name__=='__main__':unittest.main()
