import copy
import hashlib
import json
import os
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import persistent_rolling_suite_audit as audit
import test_persistent_rolling as fixture
from persistent_rolling_trace_audit import audit_controller
from test_finalize_persistent_rolling_proof import metadata


def cohort():
    baseline=audit.load_baseline(Path(__file__).parent/'persistent-rolling-baseline-audit.json')
    plan,suite,terminal,_=metadata('measured')
    plan.update(dump_each=False,suite_prompt_count=12,max_new=512,prompt_tokens=baseline['rows'][0]['prompt_tokens'])
    suite['prompts']=[{k:r[k] for k in ('id','prompt_tokens','max_new')} for r in baseline['rows']]
    plan['ring_trace_limit']=max(6*(len(r['prompt_tokens'])+r['max_new']-1) for r in suite['prompts'])
    for stage in plan['stages']:stage['argv']+=['--pipeline-ring-trace-limit',str(plan['ring_trace_limit'])]
    ident=dict(model=plan['model_identity_sha256'],draft_manifest=plan['draft_model_sha256'],draft_experts=plan['draft_experts'],
        prompt=plan['prompt_tokens'],context=plan['context'],max_new=plan['max_new'],vocab=plan['vocab'],eos=plan['eos_token_ids'],
        config_sha256=plan['config_sha256'],mode=plan['mode'],check_policy='measured')
    plan['request_sha256']=hashlib.sha256(json.dumps(ident,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return plan,suite,terminal,baseline


def capture(count,eos=None):
    samples=[];original=fixture.suite.run
    def run(stages,plan,guard,output,**kwargs):
        result=original(stages,plan,guard,output,**kwargs)
        inputs=json.loads(Path(plan['suite']).read_text())['prompts']
        for row,record in zip(inputs,result['requests']):
            folder=Path(output)/f"request-{record['index']:02d}-{row['id']}"
            logs={n:[json.loads(l) for l in (folder/n).read_text().splitlines()]
                  for n in ('commands.jsonl','final-records.jsonl','provider-batches.jsonl')}
            samples.append((copy.deepcopy(plan),row,record,logs))
        return result
    with patch.object(fixture.suite,'run',side_effect=run):
        fixture.exercise(count,policy='measured',eos=eos,file_backed=True,
            first_options=dict(miss_first=(3,9),miss_second=(6,11)))
    return samples


def replay(sample,count):
    plan,row,result,logs=sample
    return audit_controller(logs['commands.jsonl'],logs['final-records.jsonl'],logs['provider-batches.jsonl'],row['prompt_tokens'],
        result['output_ids'],result['request_sha256'],count,16,97,128,epoch=result['epoch'],
        initial_sequences=result['initial_sequences'],check_policy='measured',max_new=row['max_new'])


class SuiteTests(unittest.TestCase):
    def test_bounded_reader_supports_long_suite_and_rejects_nonregular_or_duplicate(self):
        with tempfile.TemporaryDirectory(dir='/dev/shm') as folder:
            root=Path(folder);large=root/'large.json';large.write_bytes(b' '*(17*1024**2)+b'{"ok":true}')
            self.assertEqual(audit.read(large),{'ok':True})
            with patch.object(audit,'MAX_EVIDENCE',64),self.assertRaises(ValueError):audit.read(large)
            small=root/'small.jsonl';small.write_text('{"x":1,"x":1}\n')
            with self.assertRaisesRegex(ValueError,'duplicate'):audit.lines(small)
            small.write_text('{"x":1}\n')
            with patch.object(audit,'MAX_LINE',4),self.assertRaises(ValueError):audit.lines(small)
            fifo=root/'fifo';os.mkfifo(fifo)
            with self.assertRaises(ValueError):audit.read(fifo)
            symlink=root/'link';symlink.symlink_to(small)
            with self.assertRaises(OSError):audit.read(symlink)

    def test_actual5965_arrays_and_position571(self):
        plan,suite,terminal,baseline=cohort();reasons=audit.validate_suite(plan,suite,terminal,baseline)
        self.assertEqual(reasons.count('cap'),11);self.assertEqual(reasons[2],'eos')
        self.assertEqual(sum(len(r['expected_output_ids']) for r in baseline['rows']),5965)
        self.assertEqual(baseline['final_identity']['position'],571)
        self.assertEqual(baseline['negative']['candidate_rates']['median'],42.311880797977615)

    def test_oracle_policy_and_two32_relabel_refused(self):
        for change in ('oracle','prompt','dump','policy','eos','terminal','count','trace','trace-argv'):
            plan,suite,terminal,baseline=cohort()
            if change=='oracle':suite['prompts'][0]['expected_output_ids']=[5]
            elif change=='prompt':suite['prompts'][0]['prompt_tokens']=[]
            elif change=='dump':plan['dump_each']=True
            elif change=='policy':plan['verify_restore']=True
            elif change=='eos':plan['eos_token_ids']=suite['eos_token_ids']=[]
            elif change=='terminal':terminal['passed']=False
            elif change=='trace':plan['ring_trace_limit']-=1
            elif change=='trace-argv':plan['stages'][-1]['argv'][-1]='1'
            else:plan['suite_prompt_count']=2
            with self.subTest(change=change),self.assertRaises(ValueError):audit.validate_suite(plan,suite,terminal,baseline)

    def test_eos_cap_output_after_eos(self):
        self.assertEqual(audit.finish_reason([7,9],2,[9]),'eos');self.assertEqual(audit.finish_reason([7,8],2,[9]),'cap')
        for outputs,cap in (([7],2),([9,7],2),([],2),([1,2,3],2)):
            with self.assertRaises(ValueError):audit.finish_reason(outputs,cap,[9])

    def test_real_mmap_socket_early_eos_tail_and_cap_raw_replay(self):
        beyond=0
        for count in (2,4,6):
            full=capture(count)
            for sample in full:self.assertEqual(len(sample[2]['output_ids']),16);replay(sample,count)
            early=capture(count,eos=[96,full[0][2]['output_ids'][5]])
            for sample in early:
                result=replay(sample,count);self.assertEqual(len(sample[2]['output_ids']),6)
                frontier=len(sample[1]['prompt_tokens'])+len(sample[2]['output_ids'])-1
                beyond+=sum(r['position']>=frontier for r in result['created'].values())
                self.assertTrue(all(s['physical']==s['committed']==frontier and not s['pending'] for s in result['states']))
                corrupt=copy.deepcopy(sample);corrupt[3]['commands.jsonl'].pop()
                with self.assertRaises(ValueError):replay(corrupt,count)
        self.assertGreater(beyond,0,'must exercise actual speculative suffix beyond EOS frontier')

    def test_native_actual_provider_and_work(self):
        sample=capture(4)[0];plan,row,result,logs=sample;replayed=replay(sample,4);native=[];size=100;heads=0
        for batch,ctx in zip(logs['provider-batches.jsonl'],replayed['providers']):
            seed,parent=ctx['seed'],ctx['parent'];pos=seed['position'];head=pos>=len(row['prompt_tokens'])-1;heads+=head
            native.append(dict(sequence=ctx['sequence'],provider_serial=pos,target_pending_depth=len(ctx['pending']),seed_row=seed['id'],
                parent_row=parent['id'],seed_position=pos,confirmed_token=seed['token'],fixture=max(0,pos-len(row['prompt_tokens'])+2),
                parent_final_ticket=parent['row_sequence'],parent_final_commit=parent['accept_sequence'],hidden_sha256=batch['parent_hidden_sha256'],
                guesses=batch['guesses'],restored_position=pos,mutable_bytes_verified=False,snapshot_bytes=size if head else 0,
                canonical_ms=1.,capture_ms=.2 if head else 0.,recursive_ms=.5 if head else 0.,restore_ms=.2 if head else 0.))
        pending={str(d):sum(len(v['pending'])==d for v in replayed['providers']) for d in (0,1,2)}
        att=dict(provider_trace_records=len(native),provider_trace_omitted=0,provider_private_bytes=size,provider_commands=len(native),
            provider_position=len(native),provider_serial=len(native),provider_snapshot_captures=heads,provider_snapshot_restores=heads,
            provider_byteverified_restore_count=0,provider_pending_borrows={k:pending[k] for k in ('1','2')},provider_quiescent_borrows=pending['0'])
        args=(logs['provider-batches.jsonl'],native,replayed,logs['final-records.jsonl'],len(row['prompt_tokens']),att,result['request_sha256'],result['epoch'])
        self.assertFalse(audit.audit_provider(*args)['reference_recursive_predictions_compared'])
        work=audit.work_breakdown(logs['commands.jsonl'],replayed,native,len(row['prompt_tokens']))
        self.assertFalse(work['utilization_claim']);self.assertGreater(work['provider_native_ms']['canonical_ms']['count'],0)
        self.assertGreater(sum(sum(s['discarded_by_proposal_depth'].values()) for s in work['stage_native_busy_ms'].values()),0)
        native[-1]['hidden_sha256']='0'*64
        with self.assertRaises(ValueError):audit.audit_provider(*args)

    def test_even_median_observer_scope(self):
        rows=[dict(timing=dict(numerator=1,denominator_seconds=1/x)) for x in (1,2,9,10)]
        report=audit.timing_summary(rows,cohort()[-1],5.5)
        self.assertEqual(report['candidate_median'],5.5);self.assertFalse(report['matched_timing_observer']);self.assertFalse(report['certified'])
        with self.assertRaises(ValueError):audit.timing_summary(rows,cohort()[-1],9)


if __name__=='__main__':unittest.main()
