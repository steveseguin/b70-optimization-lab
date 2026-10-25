"""CPU fake workers: no process launches, GPU APIs or native output changes."""
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

import persistent_live_suite as suite


class Worker:
    def __init__(self,index,root):
        original=root/f'original{index}';original.mkdir()
        self.spec=dict(id=index,first=index==0,final=index==1,native_output=str(original),argv=['fixture','--pipeline-persistent-requests'])
        self.sequence=100+index*10
        self.sock=mock.Mock();self.command_pending=None;self.transmit=b'';self.received=b''
        self.position=80;self.draft_position=79;self.cache=[999];self.weights=object();self.requests=[]
        self.handoff=object()
    def command(self,op,token=0,position=0,fixture=0):
        self.sequence+=1;self.requests.append((op,token,position,fixture,self.sequence))
        if op==suite.RESET:
            if self.command_pending is not None:raise ValueError('worker pending')
            lines=(Path(self.spec['native_output'])/f'reset-{self.sequence}.txt').read_text().splitlines()
            if len(lines)!=2:raise ValueError('reset metadata lines')
            dest=Path(lines[0]);dest.mkdir(parents=True)
            self.position=self.draft_position=0;self.cache=[]
            receipt=dict(schema=suite.PROTOCOL,passed=True,stage_id=self.spec['id'],global_sequence=self.sequence,
                target_position=0,draft_position=0 if self.spec['first'] else None,pending_ticket=False,
                sticky_error=0,allocation_ids_preserved=True,context_extent=32,alternate_extent=32,
                counters_reset=True,trace_reset=True)
            (dest/'wavefront-reset.json').write_text(json.dumps(receipt))
        return (0,0,0,0,self.sequence,0 if self.spec['first'] else 1,self.spec['id'],int(self.spec['final']),0.,0.,0.,0.)


class PersistentTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.workers=[Worker(i,self.root) for i in range(2)]
        self.guard=mock.Mock()
        self.plan=dict(persistent_reset_protocol=suite.PROTOCOL,persistent_reset_source_sha256='a'*64,model_identity_sha256='fixed',activation_dtype='F32',
            context=64,vocab=100,max_new=3,eos=99)
        self.data=dict(schema='ownrt.persistent-cold-suite.v1',model_identity_sha256='fixed',activation_dtype='F32',prompts=[])
        for name,prompt in [('first',[1,2]),('second',[7,8,9])]:
            expected=[prompt[-1]+1,prompt[-1]+2,prompt[-1]+3]
            self.data['prompts'].append(dict(id=name,prompt_tokens=prompt,max_new=3,cached_tokens=0,
                expected_output_ids=expected,expected_output_sha256=suite.token_sha(expected)))
        self.output=self.root/'suite';self.output.mkdir()
        self.seeds=[]
    def drive(self,stages,plan,guard,output,*,initial_sequences):
        self.seeds.append(initial_sequences)
        for stage in stages:
            self.assertEqual((stage.position,stage.draft_position,stage.cache),(0,0,[]))
            self.assertFalse(hasattr(stage,'handoff'))
        model=suite.live.schedule.Wavefront(2,plan['prompt_tokens'],plan['max_new'],plan['vocab'],plan['eos'],lambda _:None)
        suite.seed_model_sequences(model,initial_sequences)
        emitted=0
        with (output/'tokens.jsonl').open('x') as out:
            while not model.done:
                commands=model.commands();self.assertTrue(commands)
                for command in commands:
                    stage=stages[command.stage]
                    self.assertEqual(command.sequence,stage.sequence+1)
                    stage.sequence=command.sequence
                    if command.op==suite.live.schedule.ROW:
                        model.complete(command,output_token=command.row.token+1 if stage.spec['final'] and command.row.fixture else None,
                            stream=None if stage.spec['final'] else b'F32')
                    else:
                        model.complete(command)
                        if command.op==suite.live.schedule.COMMIT:
                            stage.position+=1;stage.cache.append(command.row.token)
                    while emitted<len(model.emitted):
                        out.write(json.dumps(dict(index=emitted,token=model.emitted[emitted],committed_monotonic_s=time.monotonic()))+'\n')
                        emitted+=1
        return dict(output_ids=model.emitted,input_position=model.frontier)
    def test_two_cold_prompts_keep_workers_weights_and_global_sequences(self):
        identities=[id(w) for w in self.workers];weights=[w.weights for w in self.workers]
        result=suite.run_suite(self.workers,self.plan,self.guard,self.output,suite=self.data,drive=self.drive,expected_count=2,dump_each=True)
        self.assertTrue(result['passed']);self.assertEqual(result['process_launches_by_harness'],0)
        self.assertEqual([id(w) for w in self.workers],identities)
        self.assertEqual([w.weights for w in self.workers],weights)
        self.assertEqual(self.seeds[0],(101,111))
        self.assertTrue(all(a<b for a,b in zip(self.seeds[0],self.seeds[1])))
        for worker in self.workers:
            resets=[r for r in worker.requests if r[0]==suite.RESET]
            self.assertEqual(len(resets),2)
            self.assertEqual([r[1:4] for r in resets],[(0,0,0)]*2)
        self.assertEqual([r['cached_tokens'] for r in result['prompts']],[0,0])
        self.assertEqual(result['prompts'][1]['output_ids'],[10,11,12])
        self.assertEqual(result['last_prompt_id'],'second')
        self.assertEqual(result['final_input_position'],5)
        self.assertEqual(result['final_output_ids'],[10,11,12])
        self.assertEqual(result['final_output_scope'],'last prompt only')
    def test_build_gate_requires_pinned_header_and_preserves_original_plan(self):
        receipt_path=self.root/'receipt.json'
        receipt=dict(schema='ownrt.engine.build.v1',binary='/fixture/engine',binary_sha256='b'*64,sources={'pipeline/request_reset.hpp':'a'*64})
        receipt_path.write_text(json.dumps(receipt))
        plan=dict(pins={str(receipt_path):suite.base.digest(receipt_path),'/fixture/engine':'b'*64},
                  stages=[dict(argv=['engine','--pipeline-wavefront','--pipeline-live-draft'])])
        enabled=suite.enable_reset_plan(plan,receipt_path)
        self.assertEqual(enabled['persistent_reset_source_sha256'],'a'*64)
        self.assertIn('--pipeline-persistent-requests',enabled['stages'][0]['argv'])
        self.assertNotIn('--pipeline-persistent-requests',plan['stages'][0]['argv'])
        receipt['sources']={};receipt_path.write_text(json.dumps(receipt))
        plan['pins'][str(receipt_path)]=suite.base.digest(receipt_path)
        with self.assertRaisesRegex(ValueError,'lacks persistent reset'):
            suite.enable_reset_plan(plan,receipt_path)
    def test_missing_native_opt_in_never_resets(self):
        self.workers[1].spec['argv']=[]
        with self.assertRaisesRegex(ValueError,'opt-in absent'):
            suite.run_suite(self.workers,self.plan,self.guard,self.output,suite=self.data,drive=self.drive,expected_count=2)
        self.assertTrue(all(not w.requests for w in self.workers))
    def test_pending_wire_refuses_before_any_reset(self):
        self.workers[1].command_pending=object()
        with self.assertRaisesRegex(ValueError,'unresolved'):
            suite.run_suite(self.workers,self.plan,self.guard,self.output,suite=self.data,drive=self.drive,expected_count=2)
        self.assertTrue(all(not w.requests for w in self.workers))
    def test_missing_drive_hook_or_native_capability_never_resets(self):
        with self.assertRaisesRegex(ValueError,'sequence hook'):
            suite.run_suite(self.workers,self.plan,self.guard,self.output,suite=self.data,drive=lambda stages,plan,guard,output: None,expected_count=2)
        bad=dict(self.plan,persistent_reset_protocol=None)
        with self.assertRaisesRegex(ValueError,'capability'):
            suite.run_suite(self.workers,bad,self.guard,self.output,suite=self.data,drive=self.drive,expected_count=2)
        self.assertTrue(all(not w.requests for w in self.workers))
    def test_output_mismatch_stops_before_next_reset_and_retains_evidence(self):
        self.data['prompts'][0]['expected_output_ids']=[40,41,42]
        self.data['prompts'][0]['expected_output_sha256']=suite.token_sha([40,41,42])
        with self.assertRaisesRegex(ValueError,'baseline output differs'):
            suite.run_suite(self.workers,self.plan,self.guard,self.output,suite=self.data,drive=self.drive,expected_count=2)
        self.assertTrue((self.output/'suite-partial.json').exists())
        self.assertEqual(len([r for r in self.workers[0].requests if r[0]==suite.RESET]),1)
    def test_sequence_seed_rejects_used_model_and_bad_ranges(self):
        model=suite.live.schedule.Wavefront(2,[1,2],3,100,99,lambda _:None)
        with self.assertRaises(ValueError):suite.seed_model_sequences(model,(10,2**31))
        self.assertEqual([s.sequence for s in model.stages],[0,0])
        suite.seed_model_sequences(model,(10,20))
        with self.assertRaises(ValueError):suite.seed_model_sequences(model,(10,20))
    def test_second_eos_baseline_requires_explicit_stop_policy(self):
        row=self.data['prompts'][0]
        self.plan.update(vocab=248320,eos=248044)
        row['expected_output_ids']=[3,248046];row['expected_output_sha256']=suite.token_sha([3,248046])
        with self.assertRaisesRegex(ValueError,'EOS set'):suite.validate_suite(self.data,self.plan,2)
        self.plan['eos_token_ids']=[248044,248046]
        self.assertEqual(len(suite.validate_suite(self.data,self.plan,2)),2)
    def test_cold_baseline_and_prompt_identity_enforced(self):
        self.data['prompts'][1]['cached_tokens']=1
        with self.assertRaisesRegex(ValueError,'uncached'):suite.validate_suite(self.data,self.plan,2)
        self.data['prompts'][1]['cached_tokens']=0
        self.data['model_identity_sha256']='changed'
        with self.assertRaisesRegex(ValueError,'model/arithmetic'):suite.validate_suite(self.data,self.plan,2)
    def test_metric_excludes_first_token_and_refuses_nonmonotonic_evidence(self):
        path=self.root/'tokens.jsonl'
        rows=[dict(index=i,token=t,committed_monotonic_s=stamp) for i,(t,stamp) in enumerate([(1,12.),(2,12.5),(3,13.)])]
        path.write_text('\n'.join(map(json.dumps,rows)))
        result=suite.timing_from_tokens(path,[1,2,3],10.,14.)
        self.assertEqual(result['decode_tokens_per_second'],2.)
        self.assertEqual(result['full_response_seconds'],4.)
        self.assertEqual(result['first_token_seconds'],2.)
        rows[1]['committed_monotonic_s']=14.
        path.write_text('\n'.join(map(json.dumps,rows)))
        with self.assertRaisesRegex(ValueError,'monotonic'):suite.timing_from_tokens(path,[1,2,3],10.,14.)
    def test_changed_reset_receipt_fails_before_drive(self):
        original=suite.validate_reset_receipt
        def corrupt(receipt,stage,sequence):
            receipt['target_position']=1
            return original(receipt,stage,sequence)
        with mock.patch.object(suite,'validate_reset_receipt',side_effect=corrupt):
            with self.assertRaisesRegex(ValueError,'receipt identity'):
                suite.run_suite(self.workers,self.plan,self.guard,self.output,suite=self.data,drive=self.drive,expected_count=2)
        self.assertEqual(self.seeds,[])


if __name__=='__main__':unittest.main()
