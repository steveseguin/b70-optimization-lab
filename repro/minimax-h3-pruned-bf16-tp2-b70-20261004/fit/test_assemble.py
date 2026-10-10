"""CPU-only assembly/search tests. No real model weights or device imports."""
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
from types import SimpleNamespace
import unittest

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("recovery_assembly", HERE / "recover.py")
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)
import numpy as np
r.np = np


def pack(arrays):
    header, data, offset = {}, [], 0
    for key, dtype, a in arrays:
        raw = a.tobytes()
        header[key] = dict(dtype=dtype, shape=list(a.shape), data_offsets=[offset,offset+len(raw)])
        offset += len(raw)
        data.append(raw)
    text = json.dumps(header,separators=(",", ":")).encode()
    text += b" " * (-len(text) % 8)
    return struct.pack("<Q",len(text))+text, b"".join(data)


class AssemblyChecks(unittest.TestCase):
    def fixture(self, root):
        # BF16 includes signed zero and NaN payloads: copying must preserve bytes.
        weights = np.array([[0x8000,0x7fc1],[0x3f80,0x4000]],dtype="<u2")
        h,d = pack([("proj_in.weight","BF16",weights)])
        source = root/"source.safetensors"
        source.write_bytes(h+d)
        table = np.array([[1.],[-2.]],dtype="<f4")
        h,d = pack([("video_patch_proj.weight","BF16",weights),("adaln_t_table","F32",table)])
        return r.Tensors(source),h,d,table

    def test_assembler_known_hash_and_chunk_independence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            full,h,d,table=self.fixture(root)
            self.assertEqual(r.sha(h+d), "d25e2dee3db4f85047c8721f2895d636ed3643fde776fdb044ec06c58dc9ad0f")
            for chunk in (1,2):
                p=root/f"out-{chunk}"
                r.assemble_base(p,h,full,r.copy_plan(r.layout(h)[0],full),chunk)
                r.write_fits(p,h,[("adaln_t_table",table)])
                self.assertEqual(p.read_bytes(),h+d)
                self.assertEqual(r.file_sha(p),r.sha(h+d))

    def test_inverse_qkv_and_swiglu_copy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            arrays=[]
            values={}
            for i,key in enumerate(("attn.to_q.weight","attn.to_k.weight","attn.to_v.weight","ff.net.0.proj.weight")):
                a=np.arange(i*8,(i+1)*8,dtype="<u2").reshape(4,2)
                arrays.append(("transformer_blocks.0."+key,"BF16",a));values[key]=a
            h,d=pack(arrays);(root/"source").write_bytes(h+d)
            qkv=np.concatenate([values[f"attn.to_{k}.weight"] for k in "qkv"])
            w=values["ff.net.0.proj.weight"]
            h,d=pack([("blocks.0.attn.qkv_proj.weight","BF16",qkv),("blocks.0.mlp.fc1.weight","BF16",np.concatenate([w[2:],w[:2]]))])
            full=r.Tensors(root/"source")
            r.assemble_base(root/"out",h,full,r.copy_plan(r.layout(h)[0],full),1)
            self.assertEqual((root/"out").read_bytes(),h+d)

    def test_search_records_every_hash_and_keeps_only_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); full,h,d,table=self.fixture(root)
            recorded=[]
            specs=[dict(delta=x) for x in (1,0,2)]
            def fitter(full,header,spec,chunk):
                yield "adaln_t_table",table+spec["delta"]
            results=r.search_assembled(full,h,root/"matched",specs,fitter,
                lambda rows:recorded.append(len(rows)),expected=r.sha(h+d),chunk=1)
            self.assertEqual(recorded,[1,2,3])
            self.assertEqual([x["matched"] for x in results],[False,True,False])
            self.assertEqual(len({x["sha256"] for x in results}),3)
            self.assertEqual((root/"matched").read_bytes(),h+d)
            self.assertFalse(list(root.glob("h3-assemble-*")))

    def test_no_match_and_partial_fit_error_leave_no_output_or_scratch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);full,h,d,table=self.fixture(root)
            def fitter(full,header,spec,chunk):
                if spec["valid"]:
                    yield "adaln_t_table",table
            results=r.search_assembled(full,h,root/"out",[dict(valid=True),dict(valid=False)],fitter,
                                      lambda rows:None,expected="0"*64)
            self.assertIsNotNone(results[0]["sha256"])
            self.assertIsNone(results[1]["sha256"])
            self.assertIn("Missing fitted",results[1]["error"])
            self.assertFalse((root/"out").exists())
            self.assertFalse(list(root.glob("h3-assemble-*")))

    def test_layout_rejects_gaps_and_wrong_sizes(self):
        with tempfile.TemporaryDirectory() as tmp:
            _,h,_,_=self.fixture(Path(tmp))
            header=json.loads(h[8:]);header["adaln_t_table"]["data_offsets"][0]+=1
            raw=json.dumps(header).encode()
            with self.assertRaisesRegex(ValueError,"Invalid layout"):
                r.layout(struct.pack("<Q",len(raw))+raw)

    def test_nonfinite_fit_and_existing_output_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);full,h,_,table=self.fixture(root)
            p=root/"out";r.assemble_base(p,h,full,r.copy_plan(r.layout(h)[0],full))
            with self.assertRaisesRegex(ValueError,"nonfinite"):
                r.write_fits(p,h,[("adaln_t_table",table*np.nan)])
            with self.assertRaisesRegex(ValueError,"Output exists"):
                r.search_assembled(full,h,p,[],None,None)

    def test_variant_matrix_is_explicit_and_complete(self):
        variants=list(r.variant_specs())
        self.assertEqual(len(variants),72)
        self.assertEqual(len({json.dumps(x,sort_keys=True) for x in variants}),72)
        self.assertEqual({x["precision"] for x in variants},{"f32","bf16-io","bf16-acc"})
        self.assertTrue(all(x["table_size"]==1025 and x["time_range"]==[0.,1.] for x in variants))

    def test_true_bf16_accumulation_differs_from_f32(self):
        a=np.ones((1,300),np.float32);b=np.ones((300,1),np.float32)
        self.assertEqual(r.matmul(a,b,"f32")[0,0],300.)
        self.assertEqual(r.matmul(a,b,"bf16-acc")[0,0],256.)

    def test_independent_fit_produces_all_arrays_and_finite_bytes(self):
        rng=np.random.default_rng(3)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);arrays=[]
            for key,shape in (("time_embedder.linear_1.weight",(16,256)),("time_embedder.linear_1.bias",(16,)),("time_embedder.linear_2.weight",(12,16)),("time_embedder.linear_2.bias",(12,)),("transformer_blocks.0.adaln_proj.linear.weight",(4,12)),("transformer_blocks.0.adaln_proj.linear.bias",(4,))):
                arrays.append((key,"F32",rng.normal(0,.1,shape).astype("<f4")))
            h,d=pack(arrays);(root/"source").write_bytes(h+d);full=r.Tensors(root/"source")
            header={"adaln_t_table":{},"blocks.0.adaln_proj.linear.weight":{},"blocks.0.adaln_proj.linear.bias":{},"rope.inv_freq":{"shape":[16]}}
            for solver in ("svd","normal-left","normal-right"):
                variant=next(r.variant_specs(("f32",)));variant["solver"]=solver
                result=dict(r.fit_tensors(full,header,variant,2))
                self.assertEqual(set(result),set(header))
                self.assertEqual(result["adaln_t_table"].shape,(1025,8))
                self.assertEqual(result["blocks.0.adaln_proj.linear.weight"].shape,(4,8))
                self.assertTrue(all(np.isfinite(a).all() for a in result.values()))
                again=dict(r.fit_tensors(full,header,variant,2))
                self.assertTrue(all(a.tobytes()==again[k].tobytes() for k,a in result.items()))

    def test_pinned_metadata_and_layout_totals(self):
        raw=(HERE/"historical-layout.header").read_bytes()
        self.assertEqual(r.sha(raw),r.LAYOUT_SHA)
        header,size=r.layout(raw)
        self.assertEqual(size,r.HISTORICAL_BYTES)
        self.assertEqual(len(header),532)
        self.assertEqual(sum(k.endswith(".adaln_proj.linear.weight") for k in header),51)

    def test_full_official_header_mapping_covers_all_unchanged_weights(self):
        metadata=json.loads((HERE/"official-tensor-headers.json").read_text())
        entries={k:(None,0,e) for f in metadata['files'] for k,e in f['header'].items() if k!='__metadata__'}
        header,_=r.layout((HERE/"historical-layout.header").read_bytes())
        plan=r.copy_plan(header,SimpleNamespace(entries=entries))
        used={key for slices in plan.values() for key,first,last in slices}
        expected={k for k in entries if not k.startswith('time_embedder.') and '.adaln_proj.linear.' not in k and not k.startswith('norm_out.linear.')}
        self.assertEqual(used,expected)
        self.assertEqual(len(plan),428)
        self.assertEqual(len(used),532)
        self.assertEqual({k for k in used if entries[k][2]['dtype']=='F32'},
                         {p+s for p in ('proj_in','proj_out','audio_proj_in','audio_proj_out') for s in ('.weight','.bias')})
        self.assertEqual(sum(entries[k][2]['dtype']=='BF16' for k in used),524)


if __name__ == "__main__":
    unittest.main()
