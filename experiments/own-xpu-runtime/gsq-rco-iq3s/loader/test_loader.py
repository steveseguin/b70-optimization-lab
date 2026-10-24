"""Actual iq3::Model over tiny synthetic GGUFs, never model payloads/devices."""
from pathlib import Path
import copy,json,os,struct,subprocess,tempfile,unittest
import prepare_inputs as I
P=I.P
# All thirteen actual types; one BF16 HC replica is shared by both cards.
SPECS=[('output.weight','target_head',14,256,210,-1,2),('token_embd.weight','embedding',23,256,136,-1,0),('per_layer_token_embd.weight','ple_lookup',20,32,18,1,0),('blk.0.attn_qkv.weight','gdn',12,256,144,0,1),('blk.0.attn_gate.weight','gdn',13,256,176,0,1),('blk.0.ssm_out.weight','gdn',8,32,34,0,1),('blk.0.ssm_norm.weight','norms',0,4,16,0,1),('blk.0.hc_attn_down.weight','hyperconnections',30,4,8,0,3),('blk.1.ple_conv1d.weight','ple_projection',1,4,8,1,1),('blk.1.ffn_gate_exps.weight','routed_experts',22,256,82,1,1),('blk.1.ffn_up_exps.weight','routed_experts',21,256,110,1,1),('blk.1.ffn_down_exps.weight','routed_experts',42,64,18,1,1),('blk.24.ffn_gate_exps.weight','routed_experts',18,256,98,24,2)]
pack=lambda fmt,*a:struct.pack('<'+fmt,*a)
string=lambda s:pack('Q',len(s.encode()))+s.encode()


def fixture(root,change=None):
    rows=[]
    for i,(name,component,kind,n,size,layer,mask) in enumerate(SPECS):
        rows.append(dict(shard=f'shard{i%2}.gguf',name=name,component=component,type_id=kind,dimensions=[n,2],offset=0,bytes=size*2,layer=layer,mask=mask))
    if change:change(rows)
    paths=[]
    for ordinal in range(2):
        path=root/f'shard{ordinal}.gguf';paths.append(path)
        group=[r for r in rows if r['shard']==path.name];offset=0
        for r in group:r['offset']=offset;offset=(offset+r['bytes']+31)//32*32
        meta=b''.join(string(k)+pack('I',4)+pack('I',v) for k,v in [('split.no',ordinal),('split.count',2),('split.tensors.count',len(rows))])
        header=b'GGUF'+pack('IQQ',3,len(group),3)+meta
        for r in group:header+=string(r['name'])+pack('I',len(r['dimensions']))+b''.join(pack('Q',d) for d in r['dimensions'])+pack('IQ',r['type_id'],r['offset'])
        path.write_bytes(header+b'\0'*((-len(header))%32)+bytes(offset))
    return rows,paths


def auth(paths):
    out=''
    for path in paths:
        s=path.stat();out+=' '.join(map(str,[path.name,s.st_size,s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns]))+'\n'
    return out


class Loader(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.rows,self.paths=fixture(self.root)
        self.plan=self.root/'plan';self.expected=self.root/'expected';self.auth=self.root/'auth'
        self.plan.write_text(I.plan_text(self.rows));self.expected.write_text(self.plan.read_text());self.auth.write_text(auth(self.paths))
    def tearDown(self):self.tmp.cleanup()
    def run_probe(self,mode='bound',ok=True,paths=None,contains=None):
        command=[str(P/'build/loader-probe'),mode,str(self.plan),str(self.expected),str(self.auth),*map(str,paths or self.paths)]
        ran=subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertEqual(ran.returncode,0 if ok else 2,ran.stderr)
        if contains:self.assertIn(contains,ran.stderr)
        return json.loads(ran.stdout) if ok else ran.stderr
    def both(self,rows):self.plan.write_text(I.plan_text(rows));self.expected.write_text(self.plan.read_text())
    def test_all_formats_actual_bound_loader(self):
        result=self.run_probe();self.assertEqual((result['types'],result['tensors']),(13,13));self.assertEqual(result['payload_bytes_read'],0)
        totals=[sum(r['bytes'] for r in self.rows if r['mask']&(1<<c)) for c in range(2)]+[sum(r['bytes'] for r in self.rows if not r['mask'])]
        self.assertEqual(result['census'],totals);self.assertGreater(result['header_bytes_read'],0)
        self.assertEqual(self.run_probe(paths=list(reversed(self.paths)))['census'],totals)
    def test_default_replica_contract_unchanged(self):
        self.run_probe(mode='default',ok=False,contains='unexpected replica')
        def q8(rows):
            r=next(r for r in rows if r['mask']==3);r.update(type_id=8,dimensions=[32,2],bytes=68)
        self.rows,self.paths=fixture(self.root,q8);self.both(self.rows);self.auth.write_text(auth(self.paths))
        self.assertEqual(self.run_probe(mode='default')['tensors'],13)
    def test_every_expected_descriptor_field_bound(self):
        mutations={'shard':'other.gguf','name':'blk.0.fake.weight','component':'norms','type_id':8,'offset':32,'bytes':999,'layer':1,'mask':3,'dimensions':[512,2]}
        for key,value in mutations.items():
            with self.subTest(key=key):
                rows=copy.deepcopy(self.rows);rows[0][key]=value;self.plan.write_text(I.plan_text(rows));self.run_probe(ok=False,contains='admitted')
        self.plan.write_text(I.plan_text(self.rows[:-1]));self.run_probe(ok=False,contains='coverage')
        self.plan.write_text(I.plan_text(self.rows+[self.rows[0]]));self.run_probe(ok=False,contains='coverage')
    def test_actual_directory_and_placement_not_only_admission(self):
        for key,value in [('type_id',8),('dimensions',[512,2]),('bytes',999),('offset',32)]:
            with self.subTest(key=key):
                rows=copy.deepcopy(self.rows);rows[0][key]=value;self.both(rows);self.run_probe(ok=False,contains='census descriptor mismatch')
        rows=copy.deepcopy(self.rows);rows[7]['mask']=1;self.both(rows);self.run_probe(ok=False,contains='placement mask')
        rows=copy.deepcopy(self.rows);rows[0]['component']='gdn';self.both(rows);self.run_probe(ok=False,contains='component/layer')
    def test_unknown_type_refused_even_if_admission_agrees(self):
        rows=copy.deepcopy(self.rows);rows[0]['type_id']=11;self.both(rows);self.run_probe(ok=False,contains='admitted descriptor')
        self.rows,self.paths=fixture(self.root,lambda rs:rs[0].update(type_id=65535));self.both(self.rows);self.auth.write_text(auth(self.paths))
        self.run_probe(mode='default',ok=False,contains='unsupported type')
    def test_all_stat_fields_and_duplicate_identities(self):
        original=auth(self.paths)
        for i in range(1,6):
            fields=original.splitlines()[0].split();fields[i]=str(int(fields[i])+1)
            self.auth.write_text(' '.join(fields)+'\n'+original.splitlines()[1]+'\n');self.run_probe(ok=False,contains='held shard identity')
        self.auth.write_text(original.splitlines()[0]+'\n'+original.splitlines()[0]+'\n');self.run_probe(ok=False,contains='duplicate admitted shard')
        self.auth.write_text(original.splitlines()[0]+'\n');self.run_probe(ok=False,contains='exact two')
    def test_replaced_inode_symlink_and_path_coverage(self):
        self.run_probe(ok=False,paths=[self.paths[0],self.paths[0]],contains='identity set')
        original=self.paths[0];backup=self.root/'backup';original.rename(backup);original.write_bytes(backup.read_bytes())
        self.run_probe(ok=False,contains='held shard identity')
        original.unlink();original.symlink_to(backup);self.run_probe(ok=False,contains='open read-only')
    def test_split_mismatch_overlap_and_truncation_actual_parser(self):
        data=self.paths[0].read_bytes();marker=string('split.count')+pack('I',4)+pack('I',2)
        self.paths[0].write_bytes(data.replace(marker,string('split.count')+pack('I',4)+pack('I',3)));self.auth.write_text(auth(self.paths));self.run_probe(ok=False,contains='split coverage')
        self.rows,self.paths=fixture(self.root);self.both(self.rows)
        data=self.paths[0].read_bytes();second=self.rows[2]
        needle=string(second['name'])+pack('IQQIQ',2,*second['dimensions'],second['type_id'],second['offset'])
        self.assertIn(needle,data);self.paths[0].write_bytes(data.replace(needle,needle[:-8]+pack('Q',0)));self.auth.write_text(auth(self.paths));self.run_probe(ok=False,contains='overlapping tensors')
        self.rows,self.paths=fixture(self.root);self.both(self.rows)
        self.paths[1].write_bytes(self.paths[1].read_bytes()[:40]);self.auth.write_text(auth(self.paths));self.run_probe(ok=False,contains='header')
    def test_plan_parser_strict(self):
        original=self.plan.read_text()
        for text in ['',original+'garbage\n',original.replace(' 2 256 2\n',' 2 256 2 trailing\n',1)]:
            self.plan.write_text(text);self.run_probe(ok=False)
    def test_retained_real_inputs_masks_and_p195_body(self):
        I.verify_pins();record=json.loads((P/'inputs.json').read_text());self.assertEqual(record['tensor_count'],1224)
        self.assertEqual(record['placement_sha256'],I.sha(P/'placement.tsv'));self.assertEqual(record['stat_auth_sha256'],I.sha(P/'shard-auth.tsv'))
        self.assertGreater(record['replica_BF16_count'],0);self.assertGreater(record['mask_counts']['3'],0)
        overlay=json.loads((P/'overlay.json').read_text())
        self.assertTrue(all(v['body_identical'] and v['patched_body_identical'] for v in overlay['p195_compatibility'].values()))
        source=(P/'build/private/gguf.cpp').read_text()
        self.assertIn('if(expected)file->verify(*expected)',source);self.assertIn('if(admission)for(auto& s:shards)s.file->verify',source)
        self.assertIn('numeric execution forbidden',(P/'build/private/math.hpp').read_text())

if __name__=='__main__':unittest.main()
