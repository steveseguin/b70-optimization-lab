import copy
import tempfile
import unittest
from pathlib import Path
import memory_plan as M

class MemoryTests(unittest.TestCase):
    def test_census_pinned_exact(self):
        p=M.plan()
        self.assertEqual(p['census']['pinned_expert_bytes'],48_627_712_000)
        self.assertEqual(sum(x['layer_bytes'] for x in p['census']['layers']),48_627_712_000)
        self.assertEqual(p['census']['layers'][2]['expert_bytes'],2_329_600)
        self.assertEqual(p['allocation_inventory']['target_nonexpert_bytes'],5_815_529_984)
        self.assertEqual(p['device_owned_bound_bytes'],sum(p['device_categories'].values()))
        self.assertEqual(p['host_categories']['gpuactive_shadow_bound'],4*1024**3)
    def test_exact_boundary(self):
        p=M.plan();n=p['host_required_available_bytes']
        self.assertEqual(M.admit({'MemAvailable':n},p)['margin_bytes'],0)
        with self.assertRaisesRegex(ValueError,'shortage 1'):
            M.admit({'MemAvailable':n-1},p)
    def test_device_reserve_refuses(self):
        p=M.plan();p['device_margin_bytes']=-1
        with self.assertRaises(ValueError): M.admit({'MemAvailable':10**15},p)
    def test_swap_does_not_admit(self):
        with self.assertRaises(ValueError):M.admit({'MemAvailable':0,'SwapFree':10**15})
    def test_full_shadow_not_subtracted_as_existing_headroom(self):
        p=M.plan();n=p['host_required_available_bytes']
        self.assertEqual(M.admit({'MemAvailable':n,'GPUActive':100},p)['required_bytes'],n)
    def test_sensor(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'meminfo';p.write_text('MemAvailable: 12 kB\nGPUActive: 3 kB\n')
            self.assertEqual(M.meminfo(p),{'MemAvailable':12288,'GPUActive':3072})
            p.write_text('GPUActive: 3 kB\n')
            with self.assertRaises(ValueError):M.meminfo(p)

if __name__=='__main__':unittest.main()
