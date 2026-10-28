"""CPU-only exact native trace scope regression; old scope stays strict."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import tempfile
import unittest
import compare_pipeline_state as C


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


class PrefillProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'native'/'requests'/'request-test'
        self.root.mkdir(parents=True)
        self.path=self.root/'target-set.json'
        self.dump=self.root/'state-2000000000'
        self.prompt=[3,5,8,13,21]
        self.pairs=[dict(position=p,token=t,hidden_bytes=16,hidden_sha256=digest(bytes([p])))
                    for p,t in enumerate([5,8,13,21,34],1)]
        self.pair_sha=digest(json.dumps(self.pairs,sort_keys=True,separators=(',',':')).encode())
        self.identity=dict(position=6,model_sha256='a'*64,
            prompt_token_sha256=digest(b''.join(struct.pack('<I',t) for t in self.prompt)))
        self.spec=dict(schema='ownrt.pipeline-state-set.v7',verification_policy='qualification',
            ring_epoch=1,ring_request_sha256='b'*64,draft_input_identity=dict(
            draft_model_sha256='c'*64,pair_sequence_sha256=self.pair_sha))
        self.att=dict(ring_request_sha256='b'*64,ring_epoch=1,stage_id=0,
            provider_commands=5,provider_serial=5,provider_trace_omitted=0,provider_trace_records=2,
            provider_present=True,provider_snapshot_captures=2,provider_snapshot_restores=2,
            provider_byteverified_restore_count=2,trace_records=6,trace_omitted=0,rows=6,commits=6,abort_count=0)
        plan=dict(check_policy='qualification',dump_each=True,epoch=1,request_sha256='b'*64,
            model_identity_sha256='a'*64,draft_model_sha256='c'*64,provider_stage=0,
            stages=[dict(native_output=str(self.root.parent.parent))]*4,prefill_rows=2,prefill_pipeline=False,vocab=100,prompt_tokens=self.prompt)
        rows=[dict(draft_position=i,confirmed_token=p['token'],guess=-1 if i<3 else 2,
                   head=i>=3,wall_ms=1) for i,p in enumerate(self.pairs)]
        batches=[dict(provider_serial=p['position'],seed_position=p['position'],confirmed_token=p['token'],
                      hidden_sha256=p['hidden_sha256'],sequence=p['position']*4,restored_position=p['position'],
                      snapshot_bytes=64,mutable_bytes_verified=True) for p in self.pairs[3:]]
        target=[dict(op=op,position=p,sequence=i+1) for i,(p,op) in enumerate(
            [(p,op) for p in range(3,6) for op in (24,25)])]
        self.evidence=dict(schema='ownrt.prefill-trace-provenance.v1',
            selected_plan=self.write('selected-request-plan.json',plan),
            canonical_pairs=self.write('canonical-pairs.json',dict(pairs=self.pairs,sha256=self.pair_sha)),
            native_draft_rows=self.write('draft-rows.jsonl',rows,lines=True),
            native_provider_batches=self.write('ring-draft-batches.jsonl',batches,lines=True),
            provider_attestation=self.write(self.dump.name+'.ring-state.json',self.att))
        self.stage=dict(id=0,prefill_trace=self.write('ring.jsonl',target,lines=True))
        self.spec['prefill_provenance']=self.evidence

    def write(self,name,value,lines=False):
        raw=(''.join(json.dumps(v)+'\n' for v in value) if lines else json.dumps(value)).encode()
        path=self.root/name;path.write_bytes(raw)
        return dict(path=str(path),sha256=digest(raw))

    def check(self):
        return C.prefill_provenance(self.path,self.stage,self.dump,dict(stream_bytes=16),
                                    self.identity,self.spec,self.att)

    def mutate(self,key,transform,lines=False):
        ref=self.evidence[key];path=Path(ref['path'])
        value=[json.loads(r) for r in path.read_text().splitlines()] if lines else json.loads(path.read_text())
        transform(value)
        self.evidence[key]=self.write(path.name,value,lines)

    def test_valid_native_prefix_and_exact_suffix_partition(self):
        bulk,receipts=self.check()
        self.assertEqual(bulk,3)
        self.assertEqual(len(receipts),6)

    def test_original_scope_has_no_prefill_allowance(self):
        del self.spec['prefill_provenance'];del self.stage['prefill_trace']
        self.assertEqual(self.check(),(0,[]))

    def test_unbound_trace_rejected(self):
        del self.spec['prefill_provenance']
        with self.assertRaisesRegex(ValueError,'explicit provenance'):self.check()

    def test_hash_mutation_refused(self):
        Path(self.evidence['native_draft_rows']['path']).write_text('{}\n')
        with self.assertRaisesRegex(ValueError,'SHA'):self.check()

    def test_wrong_native_token_even_rehashed_refused(self):
        self.mutate('native_draft_rows',lambda rows:rows[0].update(confirmed_token=99),True)
        with self.assertRaisesRegex(ValueError,'token/position'):self.check()

    def test_invented_prefill_count_from_short_trace_refused(self):
        self.mutate('native_draft_rows',lambda rows:rows.pop(),True)
        with self.assertRaisesRegex(ValueError,'completeness'):self.check()

    def test_native_batch_hidden_mismatch_refused(self):
        self.mutate('native_provider_batches',lambda rows:rows[0].update(hidden_sha256='f'*64),True)
        with self.assertRaisesRegex(ValueError,'actual pair'):self.check()

    def test_omitted_target_trace_refused(self):
        self.att['trace_omitted']=1
        self.evidence['provider_attestation']=self.write(self.dump.name+'.ring-state.json',self.att)
        with self.assertRaisesRegex(ValueError,'target trace scope'):self.check()

    def test_rehashed_prompt_not_same_input_refused(self):
        self.mutate('selected_plan',lambda plan:plan['prompt_tokens'].__setitem__(0,99))
        with self.assertRaisesRegex(ValueError,'prompt hash'):self.check()


if __name__=='__main__':unittest.main()
