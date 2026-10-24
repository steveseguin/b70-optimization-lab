"""Closed census checks; never opens model shards."""
import hashlib, json, unittest
from pathlib import Path
import census as C


class Retained(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.old=json.loads((C.P/'old-census.json').read_text())
        cls.new=json.loads((C.P/'new-census.json').read_text())
        cls.delta=json.loads((C.P/'compatibility-delta.json').read_text())
        cls.receipt=json.loads((C.P/'receipt.json').read_text())

    def test_exact_source_and_closed_artifact_hashes(self):
        for path,want in self.receipt['source_sha256'].items():
            self.assertEqual(C.sha((C.ROOT/path).read_bytes()),want,path)
        for name,record in self.receipt['artifacts'].items():
            raw=(C.P/name).read_bytes();self.assertEqual(len(raw),record['bytes']);self.assertEqual(C.sha(raw),record['sha256'])
        self.assertEqual(self.receipt['tensor_payload_bytes_read'],0)
        self.assertEqual(self.receipt['header_bytes_read'],22049047)

    def test_every_known_extent_and_projection_count(self):
        for dataset in (self.old,self.new):
            self.assertEqual(len(dataset['tensors']),1224)
            self.assertEqual(sum(r['tensors'] for r in dataset['by_type'].values()),1224)
            self.assertEqual(sum(r['tensors'] for r in dataset['by_projection_role'].values()),1224)
            shards={Path(s['path']).name:s for s in dataset['shards']}
            for t in dataset['tensors'].values():
                name,block,size=C.TYPES[t['type_id']]
                self.assertEqual(name,t['type']);self.assertEqual(t['dimensions'][0]%block,0)
                self.assertEqual(t['bytes'],t['elements']//block*size)
                self.assertGreaterEqual(t['reserved_span_bytes'],t['bytes'])
                self.assertLessEqual(t['file_offset']+t['reserved_span_bytes'],shards[t['shard']]['file_bytes'])
                self.assertGreaterEqual(t['file_offset'],shards[t['shard']]['data_start'])
            self.assertEqual(sum(t['bytes'] for t in dataset['tensors'].values()),sum(r['known_payload_bytes'] for r in dataset['by_type'].values()))

    def test_names_shapes_architecture_and_complete_tokenizer_hashes(self):
        self.assertEqual(set(self.old['tensors']),set(self.new['tensors']))
        self.assertEqual(self.delta['added_tensors'],[]);self.assertEqual(self.delta['removed_tensors'],[])
        self.assertEqual(self.delta['shape_changes'],{});self.assertEqual(len(self.delta['type_changes']),695)
        for key,value in self.old['metadata'].items():
            if key.startswith(('qwen4exp.','tokenizer.')) or key=='general.architecture':
                self.assertEqual(value,self.new['metadata'][key],key)
        self.assertEqual(self.new['metadata']['tokenizer.ggml.tokens']['value']['count'],248320)
        self.assertEqual(self.new['metadata']['qwen4exp.ple.eos_token_id']['value'],248044)
        self.assertEqual(self.new['metadata']['tokenizer.ggml.eos_token_id']['value'],248046)
        self.assertEqual(self.delta['metadata_added'],{});self.assertEqual(self.delta['metadata_removed'],{})
        self.assertEqual(len(self.delta['metadata_changed']),8)

    def test_q2_and_embedding_head_exact_contract(self):
        t=self.new['tensors'];q2=[n for n,v in t.items() if v['type_id']==42]
        self.assertEqual(q2,[f'blk.{i}.ffn_down_exps.weight' for i in (1,8,10,12,13,20,21,30,36)])
        for n in q2:self.assertEqual((t[n]['dimensions'],t[n]['bytes']),([640,2560,512],235929600))
        self.assertEqual((t['token_embd.weight']['type'],t['token_embd.weight']['dimensions'],t['token_embd.weight']['bytes']),('IQ4_XS',[2560,248320],337715200))
        self.assertEqual((t['output.weight']['type'],t['output.weight']['dimensions'],t['output.weight']['bytes']),('Q6_K',[2560,248320],521472000))
        self.assertFalse(any('mtp' in n.lower() or 'nextn' in n.lower() for n in t))


if __name__=='__main__':unittest.main()
