import copy, json, subprocess, tempfile, unittest
from pathlib import Path
import bridge as B


class Bridge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old,cls.new,cls.roles=B.pinned_inputs()
        cls.rows=B.admit(cls.new,cls.new,cls.roles)
        cls.binary=B.P/'build/graph-bridge'

    def invoke(self,actual,expected=None,context='4096'):
        with tempfile.TemporaryDirectory(dir=B.P/'build') as tmp:
            a=Path(tmp)/'actual.tsv';e=Path(tmp)/'expected.tsv'
            B.export(actual,a);B.export(actual if expected is None else expected,e)
            return subprocess.run([str(self.binary),str(a),str(e),context],capture_output=True,text=True,timeout=20)

    def test_metadata_and_shard_mutation_refused(self):
        for field in ('metadata','shards'):
            bad=copy.deepcopy(self.new)
            if field=='metadata':bad[field]['qwen4exp.expert_count']['value']=256
            else:bad[field][0]['header_sha256']='0'*64
            with self.assertRaises(ValueError):B.admit(bad,self.new,self.roles)

    def test_name_type_shape_extent_and_offset_mutations_refused(self):
        name='blk.1.ffn_down_exps.weight'
        for field,value in [('type_id',999),('type','IQ3_S'),('dimensions',[640,2561,512]),('bytes',1),('file_offset',0),('shard','other.gguf')]:
            bad=copy.deepcopy(self.new);bad['tensors'][name][field]=value
            with self.assertRaises(ValueError):B.admit(bad,self.new,self.roles)
        bad=copy.deepcopy(self.new);bad['tensors'].pop(name)
        with self.assertRaises(ValueError):B.admit(bad,self.new,self.roles)

    def test_actual_cpp_directory_duplicate_unknown_and_wrong_extent(self):
        for rows in (self.rows+[self.rows[0]], [dict(t,type='UNKNOWN_999') if i==0 else t for i,t in enumerate(self.rows)], [dict(t,bytes=t['bytes']+1) if i==0 else t for i,t in enumerate(self.rows)]):
            result=self.invoke(rows,self.rows)
            self.assertNotEqual(result.returncode,0);self.assertEqual(result.stdout,'')

    def test_actual_cpp_frozen_missing_extra_and_type_refusal(self):
        for rows in (self.rows[:-1],self.rows+[dict(self.rows[0],name='unexpected.weight')],[dict(t,type='F32',bytes=t['bytes']*2) if i==0 else t for i,t in enumerate(self.rows)]):
            self.assertNotEqual(self.invoke(rows,self.rows).returncode,0)

    def test_actual_geometry_and_builder_shape_checks(self):
        # Supply the changed directory as both inputs so only the actual
        # geometry/Builder checks, not our frozen equality guard, reject it.
        for name,dims in [('token_embd.weight',[2560,248321]),('blk.4.attn_qkv.weight',[2560,10241]),('blk.4.hc_attn_norm.weight',[10241])]:
            rows=copy.deepcopy(self.rows)
            for t in rows:
                if t['name']==name:
                    old_elements=1;new_elements=1
                    for x in t['dimensions']:old_elements*=x
                    for x in dims:new_elements*=x
                    t['bytes']=t['bytes']*new_elements//old_elements;t['dimensions']=dims
            self.assertNotEqual(self.invoke(rows).returncode,0,name)

    def test_context_refuses_zero_negative_excess_and_trailing(self):
        for value in ('0','-1','32769','4096oops'):
            self.assertNotEqual(self.invoke(self.rows,context=value).returncode,0)

    def test_actual_retained_topology_every_launch_and_buffer(self):
        old=B.read(B.P/'old-plan.json');new=B.read(B.P/'new-plan.json')
        self.assertTrue(B.same_topology(old,new))
        result=B.validate_graph(new,self.rows)
        self.assertEqual(len(result['tensor_placement']),1224)
        self.assertEqual({l['card'] for l in new['launches']},{0,1})
        self.assertEqual(sum(l['op']=='handoff' for l in new['launches']),1)
        self.assertEqual(sum(l['op']=='handoff_result' for l in new['launches']),1)
        self.assertEqual(sum(l['op']=='gdn' for l in new['launches']),36)
        self.assertEqual(sum(l['op']=='qsa_attention' for l in new['launches']),12)
        self.assertEqual(sum(l['op']=='ple_hash' for l in new['launches']),1)
        self.assertFalse(result['native_admitted'])

    def test_actual_binding_mask_and_weight_reference_mutation_refused(self):
        plan=B.read(B.P/'new-plan.json')
        bad=copy.deepcopy(plan);bad['launches'][0]['inputs'].append('no-such-buffer')
        with self.assertRaises((KeyError,ValueError)):B.validate_graph(bad,self.rows)
        bad=copy.deepcopy(plan);next(l for l in bad['launches'] if l['weights'])['weights'][0]='no-such-weight'
        with self.assertRaises((KeyError,ValueError)):B.validate_graph(bad,self.rows)
        bad=copy.deepcopy(plan);next(b for b in bad['buffers'] if b['card']==0 and b['name'].startswith('blk.'))['card']=1
        with self.assertRaises(ValueError):B.validate_graph(bad,self.rows)


if __name__=='__main__':unittest.main()
