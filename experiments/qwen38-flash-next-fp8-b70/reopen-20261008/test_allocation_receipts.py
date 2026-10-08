"""CPU snapshots, global staging lifetimes and actual process serialization."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from test_overlay_cpu import guard, Tensor

HERE=Path(__file__).resolve().parent


class Stored:
    def __init__(self, address, size, device='cpu', pinned=False):
        self.address,self.size=address,size
        self.device=types.SimpleNamespace(type=device)
        self.pinned=pinned
    def untyped_storage(self):return self
    def data_ptr(self):return self.address
    def numel(self):return self.size
    def nbytes(self):return self.size
    def is_pinned(self):return self.pinned


class AllocationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.env=patch.dict(os.environ,{'B70_SCREEN1B':'1','B70_SCREEN1B_STATE_DIR':self.tmp.name});self.env.start()
        self.mem=patch.object(guard,'memory',return_value={'MemTotal':128<<30,'MemAvailable':110<<30});self.mem.start()
        guard._cancelled=False;guard._models.clear();guard._tables.clear()
    def tearDown(self):
        self.mem.stop();self.env.stop();self.tmp.cleanup();guard._models.clear();guard._tables.clear();guard._cancelled=False
    def test_snapshot_deduplicates_uva_and_includes_actual_geometry(self):
        host=Stored(100,160,'cpu',True);uva=Stored(200,160,'xpu');uva._screen1b_host_storage=host
        expert=Stored(300,400,'xpu');expert._q38_host_cpu=Stored(400,320,'cpu',True);expert._q38_base_table=Stored(500,8,'xpu')
        model=types.SimpleNamespace(named_parameters=lambda:[('embed_tokens.weight',uva),('draft.embed_tokens.weight',uva),('mlp.experts.weight',expert)],named_buffers=lambda:[])
        cache_slab=Stored(600,480,'cpu',True);stage=Stored(700,320,'cpu',True);stage.shape=(1,2,160)
        store=types.SimpleNamespace(rows=64,width=160,start=0,end=16,index_sha256='index',header_sha256={'file':'header'},resident_bytes=lambda:4096)
        cache=types.SimpleNamespace(store=store,buffer=bytearray(480),capacity=3,hits=2,misses=3,evictions=1)
        embedding=types.SimpleNamespace(_screen1b_cache=cache,_screen1b_cache_slab=cache_slab,_screen1b_step_host=stage,_screen1b_step_device=Stored(800,320,'xpu'),_screen1b_step_capacity=1)
        guard._tables[1]=types.SimpleNamespace(ngram_embedding=embedding)
        dist=types.ModuleType('vllm.distributed');dist.get_tensor_model_parallel_rank=lambda:2
        import test_ple_mmap
        with patch.dict(sys.modules,{'vllm.distributed':dist,'vllm.screen1b_ple':test_ple_mmap.a}):
            guard.allocation_snapshot(model,contract_path=HERE/'memory-contract.json',extra_tensor_groups={'kv_and_recurrent_cache':[expert,Stored(900,64,'xpu')]})
        receipt=json.loads((self.root/'allocations-rank2.json').read_text());g=receipt['groups']
        self.assertEqual(g['input_embedding']['pinned_bytes'],160)
        self.assertEqual(g['input_embedding']['device_bytes'],0)
        self.assertEqual(g['experts']['pinned_bytes'],320)
        self.assertEqual(g['experts']['device_bytes'],408)
        self.assertEqual(g['kv_and_recurrent_cache']['device_bytes'],64)
        self.assertEqual(g['PLE_mmap_layer1']['mmap_resident_bytes'],4096)
        self.assertEqual(receipt['actual_runtime_inputs']['PLE']['owned_rows'],[0,16])
        self.assertEqual(receipt['actual_runtime_inputs']['PLE']['step_heads'],2)
        self.assertIsNone(receipt['untracked_runtime_driver_graph_bytes'])
        self.assertEqual(len(list(self.root.glob('allocations-rank2-load_complete-*.json'))),1)
    def test_retained_conversion_leaves_headroom_for_chunked_copy(self):
        import contextlib
        torch=types.ModuleType('torch');torch.no_grad=contextlib.nullcontext;torch.accelerator=types.SimpleNamespace(synchronize=lambda:None)
        Tensor.copies.clear()
        with patch.object(guard,'COPY_LIMIT',32),patch.dict(sys.modules,{'torch':torch}):
            token=guard.reserve_staging(8,'retained host conversion')
            guard.bounded_copy(Tensor((20,2)),Tensor((20,2)))
            self.assertGreater(len(Tensor.copies),1)
            self.assertTrue(all(c[2]<=24 for c in Tensor.copies))
            state=json.loads((self.root/'staging-live.json').read_text());self.assertLessEqual(state['peak_bytes'],32)
            guard.release_staging(token)
    def test_multiple_tables_refuse_total_cache_growth(self):
        guard.register_ple('model.layers.1.ple',object())
        with self.assertRaisesRegex(RuntimeError,'one PLE table'):
            guard.register_ple('model.layers.2.ple',object())
    def test_two_processes_serialize_allocation_sections(self):
        code='''import importlib.util,sys,time,json
from pathlib import Path
spec=importlib.util.spec_from_file_location('g',sys.argv[1]);g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
g.memory=lambda:{'MemTotal':128<<30,'MemAvailable':110<<30}
with g.admission('test'):
    start=time.monotonic();time.sleep(.05);end=time.monotonic()
Path(sys.argv[2]).write_text(json.dumps([start,end]))
'''
        procs=[subprocess.Popen([sys.executable,'-c',code,str(HERE/'overlay/vllm/screen1b_guard.py'),str(self.root/f'p{i}.json')],env=os.environ.copy()) for i in range(2)]
        for proc in procs:self.assertEqual(proc.wait(timeout=10),0)
        intervals=sorted(json.loads((self.root/f'p{i}.json').read_text()) for i in range(2))
        self.assertLessEqual(intervals[0][1],intervals[1][0])


if __name__=='__main__':unittest.main()
