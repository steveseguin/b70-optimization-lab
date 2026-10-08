"""CPU-only exact-pin policy, row layout and slab-alternative comparison.

Ordinary CPU tensors emulate storage. No pin_memory call or device operation.
The selected implementation is the allocator knob, not a new slab allocator.
"""
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import calibration
import memory_plan
import screen
from placement_plan import v5
from test_overlay_cpu import guard

ENV = dict.fromkeys(guard.PINNED_ALLOC_ENVS, guard.PINNED_ALLOC_CONF)


class PinnedPolicyTests(unittest.TestCase):
    def test_exact_large_and_cached_small_boundaries(self):
        with patch.dict(os.environ, ENV):
            for n in (0, 1, 1025, 2**20, 2**20+1, 196608000, 317849600, 1073741824):
                receipt = guard.pinned_allocation_bytes(n)
                rounded = 1 << (n-1).bit_length() if n else 0
                self.assertEqual(receipt['default_rounded_bytes'], rounded)
                self.assertEqual(receipt['allocator_request_bytes'], n if n > 2**20 else rounded)
                self.assertFalse(receipt['allocator_bytes_measured'])
                self.assertEqual(receipt['payload_bytes'], n)

    def test_invalid_sizes(self):
        for n in (-1, 1.5, True):
            with self.assertRaises(ValueError): guard.pinned_allocation_bytes(n)

    def test_incomplete_alias_policy_never_gets_exact_prediction(self):
        for key in ENV:
            with patch.dict(os.environ, {**ENV, key:'pinned_max_round_threshold_mb:1'}):
                self.assertEqual(guard.pinned_allocation_bytes(196608000)['allocator_request_bytes'], 268435456)

    def test_launch_sets_all_aliases_before_import_for_every_mode(self):
        with patch.dict(os.environ, dict.fromkeys(ENV, 'wrong')):
            for mode in ('mtp0', 'mtp1', 'mtp3', 'calibrate-load'):
                command=screen.launch(NS(mode=mode,port=19988),Path('/tmp/unused'))
                ident=memory_plan.launch_identity(command)
                self.assertEqual(ident['pinned_allocator_environment'], {key:[value] for key,value in ENV.items()})

    def test_entrypoint_rejects_missing_or_conflicting_aliases_before_python(self):
        base={'NEOReadDebugKeys':'1','EnableDeferBacking':'0','B70_SCREEN1B':'1',**ENV}
        for key in ENV:
            for value in (None,'pinned_max_round_threshold_mb:1'):
                env=base.copy()
                if value is None: del env[key]
                else: env[key]=value
                result=subprocess.run(['/bin/bash',str(screen.HERE/'container-entrypoint.sh'),'--execute','serve','/model'],env=env,capture_output=True,text=True,timeout=5)
                self.assertEqual(result.returncode,2)
                self.assertIn('requires exact large pinned allocations',result.stderr)

    def test_96gb_command_and_receipt_keep_normal_admission(self):
        command=screen.launch(NS(mode='calibrate-load',port=19988,loading_ram_guard_gb=96),Path('/tmp/unused'))
        self.assertEqual(calibration.loading_guard_bytes(command),96000000000)
        self.assertEqual(calibration.HOST_LIMIT,90000000000)
        self.assertEqual(guard.PRESSURE_LIMIT,80000000000)

    def test_guard_96gb_exact_boundary_and_first_cause(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                'B70_SCREEN1B':'1','B70_SCREEN1B_STATE_DIR':tmp,
                guard.CALIBRATION_GUARD_ENV:'96000000000'}), \
             patch.object(guard,'_cancelled',False), \
             patch.object(guard,'memory',return_value={'MemTotal':124179132416,'MemAvailable':28179132417}):
            guard.check_admission(1)
            with self.assertRaisesRegex(guard.LoadCancelled,'96 GB pressure'):
                guard.check_admission(2)

    def test_snapshot_reports_exact_and_old_rounded_bytes_without_allocating_them(self):
        import sys
        import tempfile
        import types
        from test_allocation_receipts import Stored
        import test_ple_mmap
        host=Stored(512,196608000,'cpu',True)
        model=NS(named_parameters=lambda:[('mlp.experts.weight',host)], named_buffers=lambda:[])
        dist=types.ModuleType('vllm.distributed'); dist.get_tensor_model_parallel_rank=lambda:0
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {
                **ENV,'B70_SCREEN1B':'1','B70_SCREEN1B_STATE_DIR':tmp}), \
             patch.object(guard,'_models',[]), patch.object(guard,'_tables',{}), \
             patch.object(guard,'memory',return_value={}), \
             patch.dict(sys.modules,{'vllm.distributed':dist,'vllm.screen1b_ple':test_ple_mmap.a}):
            guard.allocation_snapshot(model,contract_path=screen.HERE/'memory-contract.json')
            receipt=json.loads((Path(tmp)/'allocations-rank0.json').read_text())
            row=receipt['groups']['experts']
            self.assertEqual(row['pinned_bytes'],196608000)
            self.assertEqual(row['allocator_request_bytes'],196608000)
            self.assertEqual(row['default_rounded_bytes'],268435456)
            self.assertFalse(row['allocator_bytes_measured'])

    def test_exact_budget_matches_saved_anchor_without_double_counting(self):
        import attempt7_budget
        budget,planner=attempt7_budget.build()
        self.assertEqual(budget['removed_padding_bytes'],24248844288)
        self.assertEqual(budget['steady_pressure_bytes'],76374190162)
        self.assertEqual(budget['loading_pressure_bytes'],76642625618)
        self.assertLess(budget['loading_plus_active_files_plus_2gib_retention_bytes'],96000000000)
        self.assertFalse(budget['prediction_is_measurement'])
        self.assertFalse(budget['placement_changed'])
        self.assertIsNone(planner['host_peak_bytes'])

    def test_planner_keeps_old_rounding_without_complete_policy(self):
        command=screen.launch(NS(mode='calibrate-load',port=19988),Path('/tmp/unused'))
        for key in ENV:
            changed=command.copy()
            changed[changed.index(key+'='+ENV[key])]=key+'=pinned_max_round_threshold_mb:1'
            pred=memory_plan.build_prediction(changed)
            self.assertEqual(pred['illustrative_components']['pinned_allocator_rounding_bytes'],24249237504)

    def test_source_snapshot_hashes_and_allocator_mechanism(self):
        import hashlib
        root=screen.HERE/'evidence/torch-2.13-pinned-allocator'
        for name,row in json.loads((root/'sources.json').read_text()).items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),row['sha256'])
        host=(root/'CachingHostAllocator.h').read_text()
        self.assertIn('size <= pinned_max_cached_size()',host)
        self.assertIn('size > pinned_max_cached_size()',host)
        self.assertIn('size <= pinned_max_round_threshold()',host)
        self.assertIn('kHostAlignment = 512',(root/'CachingHostAllocator.cpp').read_text())

    def test_synthetic_separate_and_aligned_slab_views_have_identical_bytes_and_addresses(self):
        import torch
        # Comparison of the alternative requested by the owner. Float8 payload
        # is compared as bytes so NaNs, sign bits and all encodings are covered.
        for dtype in (torch.uint8,torch.float8_e4m3fn,torch.bfloat16):
            itemsize=torch.empty((),dtype=dtype).element_size()
            shapes=((3,2,256),(5,1,256))
            separate=[]
            for i,shape in enumerate(shapes):
                raw=(torch.arange(torch.tensor(shape).prod().item()*itemsize,dtype=torch.int64)+37*i).to(torch.uint8)
                separate.append(raw.view(dtype).view(shape))
            sizes=[t.numel()*itemsize for t in separate]
            backing=torch.empty(sum(sizes)+511,dtype=torch.uint8)
            start=(-backing.data_ptr())%512
            slab=backing[start:start+sum(sizes)]
            offset=0
            for source,size in zip(separate,sizes):
                view=slab[offset:offset+size].view(dtype).view(source.shape)
                view.view(torch.uint8).copy_(source.view(torch.uint8))
                self.assertTrue(torch.equal(view.view(torch.uint8),source.view(torch.uint8)))
                self.assertTrue(view.is_contiguous())
                self.assertEqual(view.stride(),source.stride())
                self.assertEqual(view.data_ptr()%512,0)
                self.assertEqual(view.untyped_storage().data_ptr(),backing.untyped_storage().data_ptr())
                resident=torch.empty(size+511,dtype=torch.uint8)
                base=resident.data_ptr()+(-resident.data_ptr())%512
                host_rows=list(range(1,2*source.shape[0],2))
                resident_rows=list(range(0,2*source.shape[0],2))
                row_bytes=source[0].numel()*itemsize
                table=v5.offsets(base,view.data_ptr(),resident_rows,host_rows,row_bytes,itemsize)
                for row,logical in enumerate(host_rows):
                    self.assertEqual(base+table[logical]*itemsize,view[row].data_ptr())
                    self.assertTrue(torch.equal(view[row].view(torch.uint8),source[row].view(torch.uint8)))
                offset+=size
            self.assertEqual(offset,sum(sizes))


if __name__=='__main__': unittest.main()
