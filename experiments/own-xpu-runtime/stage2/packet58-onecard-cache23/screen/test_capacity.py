"""packet58-cache23 capacity policy tests (CPU; no device data)."""
import json,tempfile,unittest
from pathlib import Path
import device_memory as D
import memory_plan as M
import views as V
P=Path(__file__).resolve().parent


class Capacity(unittest.TestCase):
    def test_maximum_retains_every_allowance(self):
        p=M.window_plan('WSCREEN');plan=json.loads((P/'memory-plan.json').read_text()) if (P/'memory-plan.json').exists() else json.loads((P.parent/'memory-plan.json').read_text())
        self.assertEqual(sum(p['device_categories'].values())+240,p['device_owned_bound_bytes'])
        self.assertEqual(p['device_categories'],plan['device_categories'])
        self.assertEqual(p['device_categories']['expert_cache_arena'],V.ALLOCATION_BYTES)
        self.assertEqual(V.ALLOCATION_BYTES,23049601024);self.assertEqual(V.ALLOCATION_BYTES%256,0)
        self.assertEqual(V.ALLOCATION_BYTES-V.USABLE['max'],1496871424)
        self.assertEqual(p['device_margin_bytes'],240);self.assertEqual(p['physical_margin_bytes'],0)
        self.assertEqual(p['device_owned_bound_bytes'],32_000_000_000-1_500_000_000-p['driver_allowance_bytes'])
        self.assertEqual(p['driver_allowance_bytes'],671088640)
        self.assertGreaterEqual(p['driver_allowance_bytes'],plan['driver_overhead_measured_bytes']['value'])
        t=plan['transient_measured'];c=p['device_categories']
        self.assertGreaterEqual(c['control_transaction_bound'],t['operator_scratch_peak'])
        self.assertGreaterEqual(c['workspace_bound'],t['other_workspace_peak'])
        self.assertGreaterEqual(c['transfer_bound'],t['device_transfer_lifetime_peak'])
        self.assertEqual(c['control_transaction_bound']+c['workspace_bound']+c['transfer_bound'],784567808)
        self.assertEqual(c['target_4k_bf16_kv_index'],116391936);self.assertEqual(c['target_recurrent'],59019280)
        self.assertLessEqual(plan['peaks_after_growth']['allocate_peak_bytes'],p['device_owned_bound_bytes'])
        self.assertLessEqual(plan['peaks_after_growth']['drm_projection_bytes'],30_500_000_000)

    def test_reserve_driver_and_guard_never_reduced(self):
        p=M.window_plan('WSCREEN')
        self.assertEqual(p['device_reserve_bytes'],1_500_000_000)
        self.assertGreater(p['driver_allowance_bytes'],536870912)
        self.assertTrue(D.observe([],Path('/nonexistent'))['passed'])
        self.assertEqual(D.observe([],Path('/nonexistent'))['reserve_bytes'],1_500_000_000)

    def test_admission_boundary(self):
        p=M.plan();required=p['host_required_available_bytes']
        self.assertEqual(required,100487123456)
        self.assertTrue(M.admit({'MemAvailable':required},p)['passed'])
        with self.assertRaises(ValueError):M.admit({'MemAvailable':required-1},p)
        self.assertEqual(M.window_plan('K1')['host_required_available_bytes'],12*1024**3)

    def test_fixed_maintenance_and_capacity_rows(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'views.tsv'
            for mode in ('serial','overlap'):
                V.write_table(p,'resident',mode)
                rows=[line.split() for line in p.read_text().splitlines()]
                self.assertEqual([r[0] for r in rows],['A0','B0','A1','B1','A2'])
                self.assertEqual([r[3] for r in rows],[mode]*5)
                self.assertEqual([r[4] for r in rows],['max','max23','max','max23','max'])
                self.assertEqual([r[5] for r in rows],['spin-kio']*5)
                self.assertEqual(len({r[1] for r in rows}),1);self.assertEqual(len({r[2] for r in rows}),1)
            with self.assertRaises(ValueError):V.write_table(p,'resident','unknown')
            with self.assertRaises(ValueError):V.bracket('mapped')

    def test_smoke_and_every_v5_view_default_to_overlap(self):
        self.assertEqual(V.DEFAULT_MAINTENANCE,'overlap')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'views.tsv'
            for candidate in ('smoke','resident'):
                V.write_table(p,candidate)
                rows=[line.split() for line in p.read_text().splitlines()]
                self.assertEqual([r[3] for r in rows],['overlap']*len(V.bracket(candidate)))
                self.assertEqual([r[4] for r in rows],[cap for _,cap in V.bracket(candidate)])

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
