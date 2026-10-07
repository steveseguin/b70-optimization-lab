"""CPU-only historical retrieval checks. Every generated response is a stub."""
import copy
import ast
import inspect
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import answers
import live
from snapshots import SnapshotStore, SnapshotStorageError, selection
from tasks import load_packet


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.path=Path(self.temp.name)/'snapshots';self.store=SnapshotStore(self.path,'archive')

    def test_wrong_missing_and_extra_archive_values_stay_wrong(self):
        state={'amber10':-999,'extra arbitrary key':456}
        receipt=self.store.save(1,state,'public original source','{"state":{"amber10":-999}}')
        state['amber10']=12
        reply=self.store.state_at(1,['amber10','birch11','extra arbitrary key'])
        self.assertEqual(reply['state'],{'amber10':-999,'extra arbitrary key':456})
        self.assertEqual(reply['missing_counters'],['birch11']);self.assertEqual(reply['receipt'],receipt)
        self.assertNotIn('oracle',inspect.signature(SnapshotStore.save).parameters)
        reply['state']['amber10']=0
        self.assertEqual(self.store.state_at(1)['state']['amber10'],-999)

    def test_snapshots_are_immutable_chained_and_fresh_only(self):
        first=self.store.save(1,{'amber10':3},'source1','raw1')
        second=self.store.save(2,{'amber10':4},'source2','raw2')
        self.assertEqual(second['previous_snapshot_sha256'],first['snapshot_sha256'])
        self.assertEqual(self.store.state_at(1)['state'],{'amber10':3})
        with self.assertRaises(SnapshotStorageError):self.store.save(1,{'amber10':8},'source','raw')
        with self.assertRaises(SnapshotStorageError):SnapshotStore(self.path,'archive')

    def test_tampered_state_receipt_and_missing_file_fail_closed(self):
        self.store.save(1,{'amber10':3},'source','raw');path=self.path/'batch-1.json';saved=path.read_bytes()
        for field in ('state_sha256','source_text_sha256','raw_response_sha256','previous_snapshot_sha256'):
            record=json.loads(saved);record['receipt'][field]='tampered';path.write_text(json.dumps(record))
            with self.assertRaises(SnapshotStorageError):self.store.state_at(1)
            path.write_bytes(saved)
        record=json.loads(saved);record['state']['amber10']=33;path.write_text(json.dumps(record))
        with self.assertRaises(SnapshotStorageError):self.store.state_at(1)
        path.unlink()
        with self.assertRaises(SnapshotStorageError):self.store.state_at(1)

    def test_selection_strict_types_bytes_and_single_batch(self):
        for batch in (True,False,0,-1,1.0,'1',[1,2]):
            with self.assertRaises(ValueError):selection(batch)
        for names in ([],True,'amber10',[1],[''],['a']*2,['x'*129],['é'*65],
                      [str(i) for i in range(257)],[str(i)+'x'*120 for i in range(40)]):
            with self.assertRaises(ValueError):selection(1,names)
        self.assertEqual(selection(1,['birch11','amber10']),['amber10','birch11'])
        self.assertIn('error',self.store.state_at(1))

    def test_queries_do_not_reconstruct_or_correct_from_source(self):
        self.store.save(1,{'amber10':999},'Set amber10 to 10.','actual model returned 999')
        before={p.name:p.read_bytes() for p in self.path.iterdir()}
        for _ in range(3):self.assertEqual(self.store.state_at(1)['state']['amber10'],999)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.path.iterdir()})
        self.assertNotIn('source_text',self.store.state_at(1))


class AnswerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=SnapshotStore(Path(self.temp.name)/'snapshots','archive')
        self.store.save(1,{'amber10':999},'source','raw')
        self.session=answers.new_session();self.questions=[{'id':'q','category':'history','answer_type':'int'}]
    def process(self,reply,cap=24):
        # The engine charges calls before invoking the protocol, including cached repeats.
        self.session['calls']+=1
        return answers.process(self.session,reply,self.questions,self.store,cap)

    def test_repeat_restores_cached_snapshot_without_new_retrieval(self):
        reply={'action':'state_at','batch_id':1,'counters':['amber10','birch11']}
        first=self.process(reply);second=self.process({**reply,'counters':['birch11','amber10']})
        self.assertEqual(first,second);self.assertEqual(self.session['retrievals'],1)
        self.assertEqual(self.session['calls'],2);self.assertEqual(first['missing_counters'],['birch11'])
        self.assertIn('error',self.process({'action':'state_at','batch_id':2}) or {})
        self.assertEqual(self.session['retrievals'],1)

    def test_budget_and_invalid_fields_cannot_multiplex(self):
        self.process({'action':'state_at','batch_id':1},cap=1)
        self.assertIsNone(self.process({'action':'state_at','batch_id':1,'counters':['amber10']},cap=1))
        self.assertIn('budget exhausted',self.session['feedback'])
        invalid=[{'action':'state_at','batch_id':True},{'action':'state_at','batch_id':[1,2]},
                 {'action':'state_at','batch_id':1,'query':'x'},
                 {'action':'state_at','batch':1},{'action':'state_at','batch_id':1,'counters':None},
                 {'action':'fetch','batch_id':1,'counters':['amber10']},
                 {'action':'state_at','batch_id':1,'counters':[]},
                 {'action':'state_at','batch_id':1,'counters':['amber10','amber10']}]
        for reply in invalid:
            self.assertIsNone(self.process(reply));self.assertTrue(self.session['feedback'].startswith('error:'))
        self.assertEqual(self.session['retrievals'],1)

    def test_all_twenty_four_retrievals_are_shared_without_hidden_extra_budget(self):
        for n in range(2,26):self.store.save(n,{'amber10':n},'source','raw')
        for n in range(1,25):self.assertIn('state',self.process({'action':'state_at','batch_id':n}))
        self.assertIsNone(self.process({'action':'state_at','batch_id':25}))
        self.assertEqual(self.session['retrievals'],24);self.assertEqual(self.session['calls'],25)
        self.assertIn('state',self.process({'action':'state_at','batch_id':1}))
        self.assertEqual(self.session['retrievals'],24);self.assertEqual(self.session['calls'],26)

    def test_source_only_denies_guessed_and_cached_history_but_saves_answers(self):
        reply={'action':'state_at','batch_id':1,'answers':{'q':999}}
        self.process(reply)  # Even a previously cached response cannot bypass permission.
        before=copy.deepcopy(self.session['cache'])
        with patch.object(self.store,'state_at',side_effect=AssertionError('must not retrieve')):
            response=answers.process(self.session,reply,self.questions,self.store,retrieval_mode='source-only')
        self.assertIsNone(response);self.assertIn('unavailable in source-only',self.session['feedback'])
        self.assertEqual(self.session['answers'],{'q':999});self.assertEqual(self.session['cache'],before)
        self.assertEqual(self.session['retrievals'],1)
        with self.assertRaises(ValueError):
            answers.process(self.session,reply,self.questions,self.store,retrieval_mode='unknown')


class HistoryStub(live.StubClient):
    kind='stub'
    def __init__(self,task,mode='history'):
        super().__init__(task);self.mode=mode;self.answer_calls=0;self.batch_calls={};self.seen=[]
    def __call__(self,messages,phase,batch_id):
        payload=json.loads(messages[1]['content']);self.seen.append((phase,payload))
        if phase=='answer':
            self.answer_calls+=1
            if self.mode=='forever' or self.answer_calls<=2:reply={'action':'state_at','batch_id':1}
            elif self.answer_calls==3:reply={'action':'state_at','batch_id':len(self.task['batches'])}
            else:reply={'action':'submit','answers':self.task['oracle']['answers']}
        else:
            self.batch_calls[batch_id]=self.batch_calls.get(batch_id,0)+1
            reply=json.loads(super().__call__(messages,phase,batch_id)[0])
            if self.mode=='wrong' and phase=='archive' and batch_id==1:reply['state']={'amber10':999,'extra key':7}
            if self.mode in ('reject-first','reject-all') and batch_id==1:
                if self.mode=='reject-all' or self.batch_calls[batch_id]==1:reply['memory']='x'*(live.MEMORY_LIMIT+1)
        return json.dumps(reply),{}


class EngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        data=Path(__file__).resolve().parents[3]/'data/2026-10-07-context-semantic-development'
        cls.tasks=load_packet(data/'documents.json',data/'adjudicated.json')
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.out=Path(self.temp.name)

    def test_gold_both_arms_all_documents_stub_only_and_no_oracle_leak(self):
        for task in self.tasks:
            for arm in live.ARMS:
                client=HistoryStub(task);out=self.out/f'{task["document_id"]}-{arm}'
                result=live.run_trial(task,arm,out,client)
                self.assertEqual(result['measurement_kind'],'stub');self.assertEqual(result['schema'],'history-live-trial.v1')
                self.assertEqual(result['score']['correct'],7);self.assertTrue(result['protocol_complete'])
                self.assertEqual(result['snapshot_count'],4);self.assertEqual(result['answer_protocol']['calls'],4)
                self.assertEqual(result['answer_protocol']['retrievals'],2)
                self.assertFalse(result['speed_gate_passed']);self.assertFalse(result['holdout_admitted'])
                for phase,payload in client.seen:
                    self.assertEqual('questions' in payload,phase=='answer')
                    for key in ('oracle','after_batch','state_after','checkpoint_metrics','score'):
                        self.assertNotIn(key,payload)
                    for reply in payload.get('retrieved',[]):
                        self.assertEqual(set(reply),{'action','batch_id','state','missing_counters','receipt','scope'})
                for artifact in result['artifacts'].values():self.assertEqual(artifact['sha256'],live.sha(out/artifact['path']))
                calls=[json.loads(line) for line in (out/'calls.jsonl').read_text().splitlines()]
                for index,batch in enumerate(result['batches']):
                    receipt=batch['attempts'][0]['snapshot_receipt']
                    self.assertEqual(receipt['source_text_sha256'],hashlib.sha256(task['batches'][index]['text'].encode()).hexdigest())
                    self.assertEqual(receipt['raw_response_sha256'],hashlib.sha256(calls[index]['response'].encode()).hexdigest())
                    self.assertEqual(receipt['snapshot_sha256'],live.sha(out/f'snapshots/batch-{index+1}.json'))

    def test_actual_wrong_archive_snapshot_retrieved_without_oracle_correction(self):
        client=HistoryStub(self.tasks[0],'wrong');result=live.run_trial(self.tasks[0],'archive',self.out/'trial',client)
        self.assertFalse(result['batches'][0]['state']['exact'])
        first=next(payload for phase,payload in client.seen if phase=='answer' and payload['retrieved'])
        self.assertEqual(first['retrieved'][0]['state'],{'amber10':999,'extra key':7})
        self.assertEqual(result['snapshot_count'],4)

    def test_rejected_attempt_has_no_snapshot_and_valid_retry_saves_once(self):
        for arm in live.ARMS:
            for mode in ('reject-all','reject-first'):
                out=self.out/(arm+mode);client=HistoryStub(self.tasks[0],mode)
                result=live.run_trial(self.tasks[0],arm,out,client)
                self.assertNotIn('snapshot_receipt',result['batches'][0]['attempts'][0])
                if mode=='reject-all':
                    self.assertEqual(result['snapshot_count'],0);self.assertEqual(list((out/'snapshots').iterdir()),[])
                    self.assertEqual(result['status'],'failed')
                else:
                    self.assertEqual(result['snapshot_count'],4);self.assertEqual(len(result['refusals']),1)
                    self.assertIn('snapshot_receipt',result['batches'][0]['attempts'][1])

    def test_snapshot_write_failure_after_quoted_apply_is_terminal_infrastructure(self):
        client=HistoryStub(self.tasks[0]);out=self.out/'trial'
        with patch.object(live.SnapshotStore,'save',side_effect=SnapshotStorageError('disk failed')):
            with self.assertRaises(live.InfrastructureError):live.run_trial(self.tasks[0],'quoted',out,client)
        result=json.loads((out/'result.json').read_bytes())
        self.assertEqual(result['failure_kind'],'infrastructure');self.assertEqual(result['calls'],1)
        self.assertEqual(result['refusals'],[]);self.assertEqual(result['snapshot_count'],0)
        with live.CanonicalLedger(out/'canonical.sqlite') as store:self.assertEqual(store.metadata()['applied_batches'],[1])

    def test_snapshot_read_failure_aborts_without_protocol_retry(self):
        client=HistoryStub(self.tasks[0]);out=self.out/'trial'
        with patch.object(live.SnapshotStore,'state_at',side_effect=SnapshotStorageError('tampered')):
            with self.assertRaises(live.InfrastructureError):live.run_trial(self.tasks[0],'archive',out,client)
        result=json.loads((out/'result.json').read_bytes());self.assertEqual(result['failure_kind'],'infrastructure')
        self.assertEqual(client.answer_calls,1);self.assertEqual(result['snapshot_count'],4)

    def test_unqueried_snapshot_deletion_or_tamper_fails_finalization(self):
        for arm in live.ARMS:
            for mode in ('delete','tamper','extra'):
                out=self.out/(arm+mode)
                class CorruptingStub(HistoryStub):
                    def __call__(client,messages,phase,batch_id):
                        # The normal stub queries only batches1 and4. Batch2
                        # must still be checked before finalizing success.
                        if phase=='answer' and client.answer_calls==3:
                            path=out/'snapshots/batch-2.json'
                            if mode=='delete':path.unlink()
                            elif mode=='tamper':
                                record=json.loads(path.read_bytes());record['state']['amber10']=-999
                                path.write_text(json.dumps(record))
                            else:(out/'snapshots/unexpected.json').write_text('{}')
                        return super().__call__(messages,phase,batch_id)
                client=CorruptingStub(self.tasks[0])
                with self.assertRaises(live.InfrastructureError):live.run_trial(self.tasks[0],arm,out,client)
                result=json.loads((out/'result.json').read_bytes())
                self.assertEqual(result['status'],'failed');self.assertEqual(result['failure_kind'],'infrastructure')
                self.assertEqual(result['snapshot_count'],4);self.assertEqual(result['answer_protocol']['calls'],4)
                self.assertFalse(result['protocol_complete']);self.assertTrue(result['final_answer_complete'])
                self.assertEqual(result['score']['correct'],7)
                self.assertIn('snapshot_receipt',result['batches'][1]['attempts'][0])
                self.assertTrue((out/'trace.json').is_file());self.assertTrue((out/'calls.jsonl').is_file())
                self.assertNotIn(2,[row['batch_id'] for row in result['answer_protocol']['cache'].values()])

    def test_summary_arm_refused_and_fixed_caps_unchanged(self):
        with self.assertRaises(ValueError):live.run_trial(self.tasks[0],'summary',self.out/'bad',HistoryStub(self.tasks[0]))
        self.assertEqual((live.LIMIT,live.MEMORY_LIMIT,live.MAX_RETRIEVAL,live.MAX_ANSWER_CALLS,live.MAX_INGESTION_ATTEMPTS),
                         (32768,6553,24,32,3))
        self.assertEqual(live.INGESTION_GENERATION,{'enable_thinking':False,'max_tokens':4096})
        self.assertEqual(live.ANSWER_GENERATION,{'enable_thinking':True,'reasoning_effort':'medium','max_tokens':8192})

    def test_cached_history_repeats_exhaust_same_thirty_two_answer_calls(self):
        client=HistoryStub(self.tasks[0],'forever')
        result=live.run_trial(self.tasks[0],'archive',self.out/'trial',client)
        self.assertEqual(result['status'],'failed');self.assertEqual(result['failure_kind'],'model_or_protocol')
        self.assertEqual(result['answer_protocol']['calls'],32);self.assertEqual(result['answer_protocol']['retrievals'],1)
        self.assertEqual(result['snapshot_count'],4);self.assertEqual(client.answer_calls,32)
        self.assertFalse(result['final_answer_complete']);self.assertEqual(result['score']['correct'],0)

    def test_modes_bind_identity_preserve_ingestion_and_same_snapshot_work(self):
        for arm in live.ARMS:
            observed={};snapshots={}
            for mode in answers.RETRIEVAL_MODES:
                out=self.out/(arm+mode);client=HistoryStub(self.tasks[0])
                result=live.run_trial(self.tasks[0],arm,out,client,retrieval_mode=mode)
                self.assertEqual(result['retrieval_mode'],mode)
                self.assertEqual(json.loads((out/'identity.json').read_bytes())['retrieval_mode'],mode)
                self.assertEqual(result['snapshot_count'],4);self.assertEqual(result['status'],'completed')
                self.assertEqual(result['answer_protocol']['retrievals'],0 if mode=='source-only' else 2)
                observed[mode]=[payload for phase,payload in client.seen if phase!='answer']
                snapshots[mode]={p.name:p.read_bytes() for p in (out/'snapshots').iterdir()}
                for phase,payload in client.seen:
                    if phase=='answer':self.assertEqual(payload['instruction'],answers.instruction_for(mode))
            self.assertEqual(observed['source-only'],observed['history'])
            self.assertEqual(snapshots['source-only'],snapshots['history'])

    def test_source_only_instruction_exact_frozen_bytes_and_mode_validation(self):
        frozen=Path(__file__).resolve().parent.parent/'semantic_v1/answers.py'
        tree=ast.parse(frozen.read_text())
        original=next(ast.literal_eval(node.value) for node in tree.body if isinstance(node,ast.Assign)
                      and any(isinstance(target,ast.Name) and target.id=='INSTRUCTION' for target in node.targets))
        self.assertEqual(answers.instruction_for('source-only').encode(),original.encode())
        for mode in ('both',None,False,0):
            with self.assertRaises(ValueError):
                live.run_trial(self.tasks[0],'archive',self.out/'invalid',HistoryStub(self.tasks[0]),retrieval_mode=mode)
        self.assertFalse((self.out/'invalid').exists())
        result=live.run_trial(self.tasks[0],'archive',self.out/'default',HistoryStub(self.tasks[0]))
        self.assertEqual(result['retrieval_mode'],'history')


if __name__=='__main__':unittest.main()
