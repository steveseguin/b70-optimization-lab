"""CPU-only v5 routing/storage contract and real-shape allocation receipt tests."""
import ast
import contextlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

from placement_plan import HERE, v5, storage_plan, enumerate_candidates
from dry_buffers import check_capacity, mapped_bytes, LIMIT


class PlanTests(unittest.TestCase):
    def test_rows_remain_addressable_even_if_called_cold(self):
        raw={str(r): {'0':[1,3]} for r in range(4)}
        resident,host=v5.row_plan(raw,0,0,4)
        p=NS(data=[[10],[30]],_q38_host_cpu=[[20],[40]],
             _q38_row_map={0:('resident',0),1:('host',0),2:('resident',1),3:('host',1)})
        self.assertEqual([v5.row_view(p,i)[0] for i in range(4)],[10,20,30,40])
        self.assertEqual(v5.offsets(4096,8192,resident,host,256,1),[0,4096,256,4352])

    def test_negative_host_offsets(self):
        self.assertEqual(v5.offsets(8192,4096,[0,2],[1,3],256,1),[0,-4096,256,-3840])

    def test_bad_row_partitions_and_alignment_refuse(self):
        for args in [(0,1024,[0],[0],256,1),(0,1025,[0],[1],256,1)]:
            with self.assertRaises(ValueError):v5.offsets(*args)
        for rows in [[1,1],[128],[-1],[True],list(range(128))]:
            with self.assertRaises(ValueError):v5.row_plan({str(r):{'0':rows} for r in range(4)},0,0)

    def test_no_missing_rank_fallback(self):
        with self.assertRaises(ValueError):v5.row_plan({'0':{'0':[1]}},0,0)

    def test_real_buffer_receipt_matches_formula_without_double_count(self):
        receipt=json.loads((HERE/'cpu-buffer-measurement.json').read_text())
        self.assertFalse(receipt['xpu_pinned_allocator_measured'])
        self.assertFalse(receipt['server_peak_measured'])
        self.assertEqual(sum(r['logical_buffer_bytes'] for r in receipt['ranks']),63609487360)
        for row in receipt['ranks']:
            self.assertEqual(row['rss_delta_bytes'],row['logical_buffer_bytes'])
            self.assertEqual(row['locked_delta_bytes'],row['logical_buffer_bytes'])
            self.assertEqual(row['after_release']['VmLck'],0)
            self.assertLess(row['loaded']['VmRSS'],20_000_000_000)

    def test_dry_measurement_limits_fail_before_allocation(self):
        with self.assertRaises(RuntimeError):check_capacity([{'bytes':LIMIT}],{'VmSize':1,'VmLck':0},LIMIT)
        with self.assertRaises(RuntimeError):check_capacity([{'bytes':8192}],{'VmSize':1,'VmLck':0},4096)
        self.assertEqual(mapped_bytes([{'bytes':1},{'bytes':4097}]),12288)

    def test_mtp0_does_not_imply_no_shared_pins(self):
        rows=json.loads((HERE/'host-memory-prediction.json').read_text())['candidate_table']
        self.assertEqual(rows[0]['pins_total'],rows[1]['pins_total'])
        self.assertGreater(rows[1]['conditional_static_reserve_gib_per_rank'][0],rows[0]['conditional_static_reserve_gib_per_rank'][0])
        self.assertFalse(any(r['qualifies'] for r in rows))


class FakeTensor:
    next_ptr=1<<20
    def __init__(self,shape,device='xpu',pin_memory=False,values=None):
        import math
        self.shape=tuple(shape);self.device=NS(type=device);self.pinned=pin_memory
        self.ptr=FakeTensor.next_ptr;FakeTensor.next_ptr+=((math.prod(shape)+255)//256+1)*256
        self.values=values
        self.data=self
    def element_size(self):return 1
    def numel(self):
        import math
        return math.prod(self.shape)
    def data_ptr(self):return self.ptr
    def is_pinned(self):return self.pinned
    def is_contiguous(self):return True
    def stride(self, dim=None):
        import math
        strides=tuple(math.prod(self.shape[i+1:]) for i in range(len(self.shape)))
        return strides if dim is None else strides[dim]
    def to(self,device):self.device=device;return self


class AllocationTests(unittest.TestCase):
    def allocate(self):
        calls=[]
        def empty(shape,**kw):
            calls.append((tuple(shape),kw));return FakeTensor(shape,**kw)
        # dtype is a semantic marker here; fake storage never calls torch/devices.
        def tensor_empty(shape,**kw):kw.pop('dtype',None);return empty(shape,**kw)
        def tensor(values,**kw):return FakeTensor([len(values)],device=kw['device'],values=values)
        torch=NS(empty=tensor_empty,tensor=tensor,int64='int64',
                 nn=NS(Parameter=lambda x,**kw:x),xpu=NS(device=lambda d:contextlib.nullcontext()))
        from test_overlay_cpu import guard as real_guard
        guard=NS(pinned_allocation_bytes=real_guard.pinned_allocation_bytes,admission=lambda *a:contextlib.nullcontext(),receipt=lambda *a,**k:None)
        def uva(host):
            view=FakeTensor(host.shape);view.device=device;return view
        device=NS(type='xpu')
        # Share the fake current device exactly, testing explicit affinity check.
        original=tensor_empty
        def device_empty(shape,**kw):
            t=original(shape,**kw)
            if kw.get('device','xpu')=='xpu':t.device=device
            return t
        torch.empty=device_empty
        modules={'torch':torch,'vllm':NS(screen1b_guard=guard),
                 'vllm.utils.torch_utils':NS(get_accelerator_view_from_cpu_tensor=uva)}
        layer=NS(layer_name='model.layers.0.mlp.experts')
        with patch.dict(sys.modules,modules), patch.object(v5,'layer_rows',return_value=([0,2],[1,3])):
            p=v5.allocate_weight(layer,'w13_weight',(4,256,1),'fp8')
        return layer,p,calls

    def test_allocate_only_final_sizes_and_preserve_all_logical_rows(self):
        layer,p,calls=self.allocate()
        self.assertEqual(p.shape,(2,256,1))
        self.assertEqual(p._q38_host_cpu.shape,(2,256,1))
        self.assertEqual(p._q38_num_experts,4)
        self.assertEqual(set(p._q38_row_map),set(range(4)))
        self.assertNotIn((4,256,1),[shape for shape,_ in calls])
        self.assertTrue(p._q38_host_cpu.is_pinned())

    def test_replacement_preserves_metadata_only_for_same_storage(self):
        layer,p,_=self.allocate()
        q=FakeTensor(p.shape);q.ptr=p.ptr
        layer.w13_weight=q
        v5.restore(layer)
        self.assertIs(q._q38_host_cpu,p._q38_host_cpu)
        layer.w13_weight=FakeTensor(p.shape)
        with self.assertRaises(RuntimeError):v5.restore(layer)

    def test_all_overlay_files_parse(self):
        for p in (HERE/'overlay').rglob('*.py'):
            ast.parse(p.read_text(),filename=str(p))


if __name__=='__main__':unittest.main()
