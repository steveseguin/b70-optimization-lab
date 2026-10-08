"""Small CPU-only fixtures; no accelerator discovery, driver calls or downloads."""
import ast
import gc
import importlib.util
import json
import os
from pathlib import Path
import random
import struct
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ple_test_adapter', HERE/'overlay/vllm/screen1b_ple.py')
a = importlib.util.module_from_spec(spec); spec.loader.exec_module(a)
from test_overlay_cpu import guard


def fixture(root, rows=64, width=160, parts=4):
    prefix='model.layers.1.ple_embedding.ngram_embedding'
    index, payloads = {}, []
    for shard in range(parts):
        n=rows//parts
        payload=bytes((row*37+col*13)%256 for row in range(shard*n,(shard+1)*n) for col in range(width))
        name=f'{prefix}.shard_{shard}.weight'; file=f'shard{shard}.safetensors'
        # valid safetensors padding and an unrelated tensor force unaligned rows
        header=json.dumps({'unrelated':dict(dtype='U8',shape=[3],data_offsets=[0,3]),name:dict(dtype='F8_E4M3',shape=[n,width],data_offsets=[3,3+len(payload)])}).encode()
        header+=b' '*((-len(header))%8)
        (root/file).write_bytes(struct.pack('<Q',len(header))+header+b'abc'+payload)
        index[name]=file;payloads.append(payload)
    (root/'model.safetensors.index.json').write_text(json.dumps(dict(weight_map=index)))
    return prefix,b''.join(payloads)


class MmapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.prefix,self.raw=fixture(self.root)
        self.store=a.RowStore(self.root,self.prefix,64,160,4,0,64)
        self.cache=a.ClockCache(self.store,bytearray(3*160))
    def tearDown(self):
        self.cache.close();self.tmp.cleanup()
    def gather(self, ids):
        result=bytearray(len(ids)*160);self.cache.gather_into(ids,result);return bytes(result)
    def test_random_and_forced_eviction(self):
        ids=[random.Random(271+i).randrange(64) for i in range(1000)]
        self.assertEqual(self.gather(ids),b''.join(self.raw[i*160:(i+1)*160] for i in ids))
        self.assertGreater(self.cache.evictions,100)
    def test_duplicates_boundaries_and_batch_larger_than_cache(self):
        ids=[0,0,15,16,31,32,47,48,63,0,63,63]*10
        self.assertEqual(self.gather(ids),b''.join(self.raw[i*160:(i+1)*160] for i in ids))
    def test_hit_does_not_read_file(self):
        self.gather([2])
        with patch.object(self.store,'read_row',side_effect=AssertionError('cache miss')):
            self.assertEqual(self.gather([2,2]),self.raw[320:480]*2)
    def test_nonowner_zero_and_partition_reconstructs(self):
        ids=[0,15,16,31,32,47,48,63]*2
        outputs=[]
        for rank in range(4):
            store=a.RowStore(self.root,self.prefix,64,160,4,rank*16,(rank+1)*16)
            cache=a.ClockCache(store,bytearray(160));out=bytearray(len(ids)*160)
            cache.gather_into(ids,out);outputs.append(out);cache.close()
        combined=bytes(sum(v)%256 for v in zip(*outputs))
        self.assertEqual(combined,self.gather(ids))
    def test_invalid_ids_fail_before_partial_output(self):
        for bad in (-1,64,True,1.1):
            out=bytearray(b'Z'*320)
            with self.assertRaises(IndexError):self.cache.gather_into([0,bad],out)
            self.assertEqual(out,b'Z'*320)
    def test_empty(self):self.assertEqual(self.gather([]),b'')
    def test_bad_dtype_refused(self):
        path=self.root/'shard0.safetensors';raw=path.read_bytes();path.write_bytes(raw.replace(b'F8_E4M3',b'BF16   '))
        with self.assertRaises(ValueError):a.RowStore(self.root,self.prefix,64,160,4,0,64)
    def test_missing_shard_refused(self):
        path=self.root/'model.safetensors.index.json';d=json.loads(path.read_text());d['weight_map'].pop(next(iter(d['weight_map'])));path.write_text(json.dumps(d))
        with self.assertRaises(ValueError):a.RowStore(self.root,self.prefix,64,160,4,0,64)
    def test_truncated_payload_refused(self):
        path=self.root/'shard3.safetensors';path.write_bytes(path.read_bytes()[:-1])
        with self.assertRaises(ValueError):a.RowStore(self.root,self.prefix,64,160,4,0,64)
    def test_read_error_does_not_publish_slot(self):
        with patch.object(self.store,'read_row',side_effect=OSError('read failure')):
            with self.assertRaises(OSError):self.gather([0])
        self.assertEqual(list(self.cache.row2slot),[-1]*64)
    def test_output_cap_and_shape(self):
        with self.assertRaises(ValueError):self.cache.gather_into([1],bytearray(159))
        with patch.object(a,'STAGING_LIMIT',159):
            with self.assertRaises(ValueError):self.gather([1])
    def test_metadata_and_cache_cap(self):
        actual=sum(len(v)*v.itemsize for v in (self.cache.row2slot,self.cache.slot2row,self.cache.epoch))+len(self.cache.reference)
        self.assertEqual(actual,a.metadata_bytes(64,480))
        with patch.object(a,'CACHE_PER_RANK',159):
            with self.assertRaises(ValueError):a.ClockCache(self.store,bytearray(160))
    def test_residency_is_observed_or_unknown(self):
        self.gather(list(range(64)))
        value=self.store.resident_bytes()
        self.assertTrue(value is None or 0<value<65536)
        with patch.object(Path,'read_text',side_effect=OSError('denied')):
            self.assertIsNone(self.store.resident_bytes())
    def test_checkpoint_is_unchanged(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        self.gather(list(range(64))*3)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})


class StagingTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ,{'B70_SCREEN1B':'1','B70_SCREEN1B_STATE_DIR':self.tmp.name});self.env.start()
        self.mem=patch.object(guard,'memory',return_value={'MemTotal':128<<30,'MemAvailable':110<<30});self.mem.start()
        guard._cancelled=False
    def tearDown(self):self.mem.stop();self.env.stop();self.tmp.cleanup();guard._cancelled=False
    def test_live_conversions_share_cap_and_release_after_stop(self):
        one=guard.reserve_staging(guard.COPY_LIMIT-1,'first')
        two=guard.reserve_staging(1,'second')
        with self.assertRaises(guard.LoadCancelled):guard.reserve_staging(1,'third')
        guard.release_staging(one);guard.release_staging(two)
        state=json.loads((Path(self.tmp.name)/'staging-live.json').read_text())
        self.assertEqual(state['live'],{});self.assertEqual(state['peak_bytes'],guard.COPY_LIMIT)
    def test_nested_admission_checks_growth(self):
        with guard.admission('outer'):
            with self.assertRaises(guard.LoadCancelled):
                with guard.admission('inner',100<<30):pass


# The stdlib test command still works. The complete validation run uses the
# existing ltx25-baseline interpreter, explicitly CPU tensors only; no installs.
try:
    import torch
    from safetensors import safe_open
except ImportError:
    torch=None


@unittest.skipIf(torch is None,'run with existing CPU-capable torch/safetensors interpreter')
class TensorExactnessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.prefix,self.raw=fixture(self.root)
        self.store=a.RowStore(self.root,self.prefix,64,160,4,0,64)
        self.cache=a.ClockCache(self.store,bytearray(320))
    def tearDown(self):self.cache.close();self.tmp.cleanup()
    def test_direct_safetensors_random_and_adversarial_rows(self):
        direct=[]
        for i in range(4):
            with safe_open(self.root/f'shard{i}.safetensors',framework='pt',device='cpu') as f:
                direct.append(f.get_tensor(f'{self.prefix}.shard_{i}.weight').view(torch.uint8))
        tensor=torch.cat(direct)
        ids=[0,15,16,31,32,47,48,63,63]+[random.Random(i).randrange(64) for i in range(500)]
        out=bytearray(len(ids)*160);self.cache.gather_into(ids,out)
        actual=torch.frombuffer(out,dtype=torch.uint8).reshape(-1,160)
        self.assertTrue(torch.equal(actual,tensor[ids]))
        # Original arithmetic, including every FP8 byte code (NaNs compared as
        # output bit patterns), global checkpoint BF16 -> FP32 -> BF16 scale.
        scale=torch.tensor([0.00019931793212890625],dtype=torch.bfloat16).to(torch.float32)
        for dtype in (torch.bfloat16,torch.float32):
            lhs=actual.view(torch.float8_e4m3fn).to(dtype)*scale.to(dtype)
            rhs=tensor[ids].view(torch.float8_e4m3fn).to(dtype)*scale.to(dtype)
            self.assertTrue(torch.equal(lhs.view(torch.uint8),rhs.view(torch.uint8)))
    def test_original_torch_hash_matches_cpu_and_gather(self):
        tree=ast.parse((HERE/'overlay/vllm/models/qwen4_exp/nvidia/ngram_embedding.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='Qwen4ExpNGramEmbedding')
        methods=[n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name in ('_shift_precompute','_shift_apply','compute_ngram_ids')]
        namespace={'torch':torch};exec(compile(ast.fix_missing_locations(ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),ast.ClassDef(name='Hash',bases=[],keywords=[],body=methods,decorator_list=[])],type_ignores=[])),'<original hash>','exec'),namespace)
        h=namespace['Hash']();h.ngram_size=3;h.heads_per_ngram=8;h.eos_token_id=7
        mult=[23703573157769,20109073645365,8052911324071];sizes=[3]*16;offsets=[i*3 for i in range(16)]
        h.layer_multipliers=torch.tensor(mult,device='cpu');h.ngram_heads_vocab_sizes=torch.tensor(sizes,device='cpu');h.ngram_heads_offsets=torch.tensor(offsets,device='cpu')
        # Overflow, EOS, duplicate tokens, request reuse, empty middle request,
        # rejected-draft replacement (new input each call, no history cache).
        for tokens in ([7,7,248319,3,7,2,2],[11,12,13,3,7,2,2]):
            qsl=[0,3,3,7];ctx=[[1,7],[7,7],[248319,3]]
            expected=h.compute_ngram_ids(torch.tensor(tokens,device='cpu'),torch.tensor(qsl,device='cpu'),torch.tensor(ctx,device='cpu')).tolist()
            actual=a.host_ngram_ids(tokens,qsl,ctx,mult,sizes,offsets,7,8)
            self.assertEqual(actual,expected)
            ids=[v for row in actual for v in row];out=bytearray(len(ids)*160);self.cache.gather_into(ids,out)
            with safe_open(self.root/'shard0.safetensors',framework='pt',device='cpu') as f:
                self.assertEqual(bytes(out[:160]),self.raw[ids[0]*160:(ids[0]+1)*160])
    def test_prepared_gather_clone_protects_static_buffer(self):
        e=types.SimpleNamespace(_screen1b_step_capacity=2,_screen1b_step_device=torch.arange(32,dtype=torch.uint8,device='cpu').reshape(2,2,8),weight=torch.empty(0,dtype=torch.float8_e4m3fn,device='cpu'))
        original=e._screen1b_step_device.clone();got=a.gather_prepared(e,torch.zeros((2,2),device='cpu'))
        got.view(torch.uint8).zero_();self.assertTrue(torch.equal(original,e._screen1b_step_device))
    def test_current_step_pre_forward_overwrites_old_rows(self):
        host=torch.zeros((2,2,160),dtype=torch.uint8,device='cpu')
        e=types.SimpleNamespace(_screen1b_step_capacity=2,_screen1b_step_host=host,
            _screen1b_step_device=torch.zeros_like(host),_screen1b_cache=self.cache)
        ids=torch.tensor([[0,63],[15,16]],device='cpu')
        module=types.SimpleNamespace(ngram_embedding=e,compute_ngram_ids=lambda *args:ids)
        parent=types.ModuleType('vllm');parent.screen1b_guard=types.SimpleNamespace(_tables={1:module})
        with patch.dict(sys.modules,{'vllm':parent}):
            for current in ([[0,63],[15,16]],[[32,32],[47,48]]):
                ids.copy_(torch.tensor(current,device='cpu'))
                a.pre_forward(dict(input_ids=None,query_start_loc=None,ngram_context=None))
                expected=b''.join(self.raw[i*160:(i+1)*160] for row in current for i in row)
                self.assertEqual(e._screen1b_step_device.numpy().tobytes(),expected)
    def test_real_checkpoint_boundary_bytes_without_table_allocation(self):
        root=Path('/mnt/fast-ai/llm-models/Qwen3.8-Flash-Next-FP8')
        if not root.exists():self.skipTest('local certified checkpoint unavailable')
        index=json.loads((root/'model.safetensors.index.json').read_text())['weight_map']
        name=next(n for n in index if '.ngram_embedding.shard_0.weight' in n)
        prefix=name.rsplit('.shard_',1)[0];size=2500012;rows=size*128
        # Boundaries of TP and checkpoint shards, and final padding. Each
        # mapping holds <=5 rows. No giant tensor/cache allocation or scan.
        for centre in (0,size,32*size,64*size,rows-1):
            first=max(0,centre-2);end=min(rows,centre+3)
            store=a.RowStore(root,prefix,rows,160,128,first,end)
            cache=a.ClockCache(store,bytearray(320))
            try:
                ids=list(range(first,end));out=bytearray(len(ids)*160);cache.gather_into(ids,out)
                expected=bytearray()
                for row in ids:
                    shard=row//size;key=f'{prefix}.shard_{shard}.weight'
                    with safe_open(root/index[key],framework='pt',device='cpu') as f:
                        direct=f.get_slice(key)[row%size:row%size+1].view(torch.uint8)
                        expected.extend(direct.numpy().tobytes())
                self.assertEqual(out,expected)
            finally:cache.close()
    def test_real_guard_conversion_keeps_live_storage_reservation(self):
        # Exercise actual TorchDispatchMode on CPU. The runtime synchronizer
        # is replaced so this test cannot initialize or query an accelerator.
        guard._cancelled=False
        source=torch.arange(8,dtype=torch.uint8,device='cpu')
        with patch.dict(os.environ,{'B70_SCREEN1B':'1','B70_SCREEN1B_STATE_DIR':self.tmp.name}), \
             patch.object(guard,'memory',return_value={'MemTotal':128<<30,'MemAvailable':110<<30}), \
             patch.object(guard,'synchronize'),patch.object(guard,'allocation_snapshot',new=lambda *args,**kwargs:None):
            @guard.guarded_load
            def convert():return source.to(torch.float32)
            converted=convert();view=converted[:];del converted;gc.collect()
            state=json.loads((self.root/'staging-live.json').read_text())
            self.assertEqual(sum(v['bytes'] for v in state['live'].values()),40)
            self.assertEqual(view.tolist(),list(range(8)))
            del view;gc.collect()
            self.assertEqual(json.loads((self.root/'staging-live.json').read_text())['live'],{})
    def test_storage_finalizer_survives_views(self):
        import weakref
        events=[];x=torch.zeros(4,device='cpu');weakref.finalize(x.untyped_storage(),events.append,'released')
        y=x[:];del x;gc.collect();self.assertEqual(events,[])
        del y;gc.collect();self.assertEqual(events,['released'])


if __name__=='__main__':unittest.main()
