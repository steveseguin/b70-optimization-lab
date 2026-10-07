#!/usr/bin/env python3
"""CPU-only stub transport controls; no socket or device calls."""
import asyncio
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('request_client_tested', HERE/'request_client.py')
C = importlib.util.module_from_spec(spec); spec.loader.exec_module(C)
PLAN = HERE.parent/'20261007-duration108-plan/candidate-plan.json'


class Transport:
    def __init__(self, mode=None, hook=None):
        self.mode = mode; self.hook = hook; self.posts = 0; self.polls = 0; self.events = []
        self.closed = False

    async def __aenter__(self): return self
    async def __aexit__(self, *args): self.closed = True
    async def subscribe(self, client_id): self.client_id = client_id

    async def get(self, path):
        if path == '/queue':
            return {'queue_running': [], 'queue_pending': ['other'] if self.mode == 'busy' else []}
        self.polls += 1
        if self.mode == 'history-delay' and self.polls < 3: return {}
        history = {'prompt': [1, self.pid, self.graph], 'status': self.status}
        if self.mode == 'wrong-history': history['prompt'][2] = {}
        return {self.pid: history}

    async def submit(self, graph, client_id):
        self.posts += 1; self.graph = copy.deepcopy(graph)
        names = {n['inputs']['run_name'] for n in graph.values() if 'run_name' in n['inputs']}
        self.pid = 'synthetic-' + names.pop()
        if self.mode == 'submit-error': raise OSError('transport submission uncertain')
        start = int(time.time()*1000); end = start + 1
        first = {'type': 'execution_start', 'data': {'prompt_id': self.pid, 'timestamp': start}}
        last = {'type': 'execution_success', 'data': {'prompt_id': self.pid, 'timestamp': end}}
        self.events = [first, last]
        messages = [[e['type'], e['data']] for e in self.events]
        self.status = {'status_str': 'success', 'completed': True, 'messages': messages}
        if self.mode == 'stale-terminal': self.events = [last]
        if self.mode == 'stale-start': first['data']['timestamp'] = 1
        if self.mode == 'cached': self.events.insert(1, {'type':'execution_cached','data':{'prompt_id':self.pid,'nodes':['344']}})
        if self.mode == 'error': self.events[-1] = {'type':'execution_error','data':{'prompt_id':self.pid}}
        if self.mode == 'other-events': self.events.insert(0, {'type':'execution_success','data':{'prompt_id':'other'}})
        if self.hook: self.hook()
        return {'prompt_id': self.pid, 'number': 1, 'node_errors': {}}

    async def receive(self, timeout):
        if self.mode == 'timeout':
            await asyncio.sleep(timeout); raise asyncio.TimeoutError()
        return self.events.pop(0)


class ClientControls(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.run=self.root/'server';self.run.mkdir()
        (self.root/'requests').mkdir();self.path=self.root/'contract.json';self.client_dir=self.root/'client'
        self.identity={'pid':123,'proc_start_ticks':'456','boot_id':'synthetic',
                       'model_verification_sha256':C.MODEL_SHA,'source_packet_manifest_sha256':'a'*64,
                       'server_args_sha256':'b'*64}
        self.write(self.run/'server-identity.json',self.identity)
        guard=self.root/'guard.py';guard.write_text('# synthetic sealed source fixture\n')
        self.contract={'schema':'ltx.resolution-request-client.v1','plan_sha256':C.G.PLAN_SHA,
                       'parent_manifest_sha256':C.G.PARENT_SHA,'root':str(self.root),'server_run':str(self.run),
                       'client_dir':str(self.client_dir),'plan_path':str(PLAN),'runtime_manifest_sha256':'a'*64,
                       'server_identity_sha256':C.G.sha((self.run/'server-identity.json').read_bytes()),
                       'min_free_bytes':C.MIN_FREE,'planned_write_bytes':C.WRITE_ALLOWANCE,'max_captures':22,'max_attempts':29,
                       'request_timeout_seconds':10,'capture_guard_path':str(guard),
                       'source_bindings':{str(p.resolve()):C.G.sha(p.read_bytes()) for p in
                                          [guard, HERE/'request_client.py', HERE/'reference_gate.py']}}
        self.free=60*1024**3;self.proc_calls=0;self.process_ok=True
        self.client=self.make_client();self.name=self.client.plan['requests'][0]['name']

    def write(self,path,obj):path.write_text(json.dumps(obj)+'\n')
    def process(self,identity):
        self.proc_calls+=1
        C.G.require(self.process_ok,'Synthetic reused PID')
    def make_client(self):
        self.write(self.path,self.contract)
        return C.Client(self.path,C.G.sha(self.path.read_bytes()),process_probe=self.process,free_probe=lambda _:self.free)
    def execute(self,t,name=None):return asyncio.run(self.client.execute(name or self.name,t))
    def full_client(self):
        spec=importlib.util.spec_from_file_location('schedule_fixture_source',HERE/'schedule.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        schedule=self.root/'schedule.json';self.write(schedule,module.build_schedule())
        self.contract.update(setup_schedule_path=str(schedule),setup_schedule_sha256=C.SCHEDULE_SHA,
                             phase_observation_path=str(self.run/'resolution-client-phase.json'))
        self.contract['source_bindings'][str(HERE/'schedule.py')]=C.G.sha((HERE/'schedule.py').read_bytes())
        self.client=self.make_client()
    def phase(self,row,**changes):
        phase={'native-setup':'native_reference','native-reference':'native_reference','native-repeat':'native_reference',
               'optimized-setup':'optimized_preparation','candidate-check':'optimized_preparation','timed-fast':'timing'}[row['phase']]
        value={'schema':'ltx.resolution-client-phase.v1','phase':phase,'plan_sha256':C.G.PLAN_SHA,
               'qualification_id':C.G.QUALIFICATION_ID,'runtime_manifest_sha256':'a'*64,
               'server_identity_sha256':self.contract['server_identity_sha256'],'active_request':None,'fault':False,
               'observed_at_ms':time.time_ns()//1000000,'reference_receipt_sha256':'c'*64,'candidate_receipt_sha256':'d'*64}
        value.update(changes);self.write(Path(self.contract['phase_observation_path']),value)
    def refused(self,t,name=None):
        with self.assertRaises((ValueError,RuntimeError,OSError,TimeoutError)):
            self.execute(t,name)
        if (self.client_dir/'state.json').exists():
            self.assertIsNotNone(json.loads((self.client_dir/'state.json').read_text())['halted'])

    def test_exact_graph_unchanged_evidence_and_single_submission(self):
        t=Transport();result=self.execute(t);self.assertEqual(t.posts,1);self.assertTrue(t.closed)
        row=self.client.plan['requests'][0];self.assertEqual(t.graph,row['graph'])
        req=self.root/'requests'/self.name
        self.assertEqual(json.loads((req/'prompt.json').read_text()),row['graph'])
        self.assertEqual(json.loads((req/'identity.json').read_text()),self.identity)
        for name in ['submission.json','events.jsonl','history.json','result.json']:self.assertTrue((req/name).exists())
        self.assertEqual(result['status']['status_str'],'success');self.assertGreater(self.proc_calls,2)

    def test_six_serial_requests_no_parallel_submission(self):
        transports=[]
        def factory():
            t=Transport();transports.append(t);return t
        results=asyncio.run(C.execute_native_sequence(self.client,factory))
        self.assertEqual(len(results),6);self.assertTrue(all(t.posts==1 and t.closed for t in transports))

    def test_attempted_name_not_retried_after_submission_error(self):
        t=Transport('submit-error');self.refused(t);self.assertEqual(t.posts,1)
        second=Transport()
        with self.assertRaises(ValueError):self.execute(second)
        self.assertEqual(second.posts,0)

    def test_native_queue_refused_before_submit(self):
        t=Transport('busy');self.refused(t);self.assertEqual(t.posts,0)

    def test_stale_terminal_without_current_start_refused(self):
        t=Transport('stale-terminal');self.refused(t);self.assertEqual(t.posts,1)

    def test_cached_current_request_latches_before_history(self):
        t=Transport('cached');self.refused(t);self.assertEqual(t.polls,0)

    def test_other_prompt_terminal_never_satisfies_current_request(self):
        t=Transport('other-events');self.execute(t);self.assertEqual(t.posts,1)
        records=[json.loads(s) for s in (self.root/'requests'/self.name/'events.jsonl').read_text().splitlines()]
        self.assertTrue(all(r['data']['prompt_id']==t.pid for r in records))

    def test_status_error_and_wrong_history_refuse(self):
        t=Transport('wrong-history');self.refused(t);self.assertTrue((self.root/'requests'/self.name/'history.json').exists())

    def test_fault_after_submit_blocks_followup_requests(self):
        t=Transport(hook=lambda:(self.root/'FAULT.json').write_text('{}'));self.refused(t);self.assertEqual(t.posts,1)

    def test_pid_reuse_before_submit_refuses(self):
        self.process_ok=False;t=Transport();self.refused(t);self.assertEqual(t.posts,0)

    def test_storage_initial_refusal_precedes_evidence_directory(self):
        self.free=C.MIN_FREE+C.WRITE_ALLOWANCE-1;t=Transport()
        with self.assertRaises(ValueError):self.execute(t)
        self.assertFalse(self.client_dir.exists());self.assertFalse((self.root/'requests'/self.name).exists())

    def test_pilot_admission_keeps50GiB_and_exact4GiB_write_budget(self):
        self.assertEqual(C.MIN_FREE,50*1024**3)
        self.assertEqual(C.WRITE_ALLOWANCE,4*1024**3)
        self.assertEqual((C.ATTEMPT_CAP,C.CAPTURE_CAP),(29,22))
        self.free=C.MIN_FREE+C.WRITE_ALLOWANCE
        t=Transport();self.execute(t)
        self.assertEqual(t.posts,1)

    def test_cumulative_write_allowance_not_reset_between_requests(self):
        self.execute(Transport())
        self.free-=C.WRITE_ALLOWANCE+1;t=Transport();self.refused(t,self.client.plan['requests'][1]['name'])
        self.assertEqual(t.posts,0)

    def test_history_poll_only_after_success_bounded(self):
        t=Transport('history-delay');self.execute(t);self.assertEqual(t.posts,1);self.assertEqual(t.polls,3)

    def test_timeout_never_signals_or_resubmits(self):
        self.contract['request_timeout_seconds']=1;self.client=self.make_client();t=Transport('timeout')
        self.refused(t);self.assertEqual(t.posts,1);self.assertEqual(t.polls,0)

    def test_wrong_native_order_and_candidate_phase_refused(self):
        t=Transport();self.refused(t,next(r['name'] for r in self.client.plan['requests'] if r['phase']=='candidate-check'));self.assertEqual(t.posts,0)

    def test_source_drift_after_admission_refuses(self):
        Path(self.contract['capture_guard_path']).write_text('# changed\n');t=Transport();self.refused(t);self.assertEqual(t.posts,0)

    def test_existing_request_directory_is_never_modified(self):
        p=self.root/'requests'/self.name;p.mkdir();(p/'original').write_text('keep')
        t=Transport();self.refused(t);self.assertEqual(t.posts,0)
        self.assertEqual(sorted(x.name for x in p.iterdir()),['original'])

    def test_exact_pilot_schedule29_serial_requests_with_external_phase_observations(self):
        self.full_client();posts=0
        for name in self.client.ordered_names:
            row=self.client.rows[name];self.phase(row);t=Transport();self.execute(t,name);posts+=t.posts
        self.assertEqual(posts,29)
        self.assertEqual(C.CAPTURE_CAP,22)
        self.assertEqual(sum(any(n['class_type'] in ('LTXBaselineCapture','LTXPipelineSave')
                                 for n in r['graph'].values()) for r in self.client.rows.values()),22)
        for phase,count in (('candidate-check',7),('timed-fast',7)):
            self.assertEqual(sum(self.client.rows[n]['phase']==phase for n in self.client.ordered_names),count)
        self.assertEqual(self.client.state['completed'],self.client.ordered_names)
        emitted=[r['expected_emitted_fixture'] for r in self.client.plan['requests']
                 if r['phase']=='timed-fast' and r['expected_emitted_fixture'] is not None]
        fixture_ids=[f['id'] for f in self.client.plan['fixtures']]
        self.assertEqual(len(fixture_ids),3)
        self.assertEqual(emitted,fixture_ids)
        self.assertEqual(emitted[:3],fixture_ids)
        self.assertEqual(len(emitted[3:]),0)

    def test_only_uninstrumented_block_and_retired_control_refused(self):
        self.full_client()
        phases=[self.client.rows[n]['phase'] for n in self.client.ordered_names]
        self.assertEqual(phases[-14:],['candidate-check']*7+['timed-fast']*7)
        self.assertNotIn('timed',phases)
        fast=self.ready_for_phase('timed-fast')
        name=fast['name'].replace('-timed-fast-','-timed-');t=Transport()
        self.refused(t,name)
        self.assertEqual(t.posts,0)
        self.assertFalse((self.root/'requests'/name).exists())

    def test_timing_policy_changed_request_refuses_before_submission(self):
        row=self.ready_for_phase('timed-fast');row['client_checkpoint_policy']='always';t=Transport()
        self.refused(t,row['name'])
        self.assertEqual(t.posts,0)
        self.assertFalse((self.root/'requests'/row['name']).exists())

    def ready_for_phase(self,phase):
        self.full_client();row=next(r for r in self.client.rows.values() if r['phase']==phase)
        prior=self.client.ordered_names[:self.client.ordered_names.index(row['name'])]
        self.client.acquire()
        try:
            self.client.state['completed']=list(prior);self.client.state['attempts']=list(prior)
            self.client.save_state()
        finally:self.client.release()
        self.phase(row)
        return row

    def test_always_policy_readout_counts_and_precedes_completion(self):
        writes=[];original=C.write_new
        def observe(path,value):
            if path.name=='client-policy.json':
                durable=json.loads((self.client_dir/'state.json').read_text())
                self.assertNotIn(self.name,durable['completed']);writes.append(path)
            return original(path,value)
        with patch.object(C,'write_new',side_effect=observe):self.execute(Transport())
        self.assertEqual(len(writes),1)
        report=json.loads(writes[0].read_text())
        self.assertEqual(report['schema'],'ltx.client-checkpoint-policy.v1')
        self.assertEqual(report['name'],self.name)
        self.assertEqual(report['phase'],'native-reference')
        self.assertEqual(report['policy'],'always')
        self.assertGreater(report['checkpoint_count'],0)
        self.assertEqual(report['checkpoint_count'],report['storage_save_count'])
        self.assertEqual(report['skipped_storage_save_count'],0)
        self.assertEqual(report['source_sha256'],C.G.sha((HERE/'request_client.py').read_bytes()))
        self.assertEqual(report['client_contract_sha256'],self.client.contract_sha)
        self.assertEqual(report['plan_sha256'],C.G.PLAN_SHA)

    def test_fast_skips_only_unchanged_storage_saves_and_checks_still_run(self):
        row=self.ready_for_phase('timed-fast');saves=[]
        original=self.client.save_state
        def save():saves.append(copy.deepcopy(self.client.state));return original()
        before=self.proc_calls
        with patch.object(self.client,'save_state',side_effect=save):self.execute(Transport(),row['name'])
        report=json.loads((self.root/'requests'/row['name']/'client-policy.json').read_text())
        self.assertEqual(report['policy'],'storage-change-only')
        self.assertGreater(report['checkpoint_count'],0)
        self.assertEqual(report['storage_save_count'],0)
        self.assertEqual(report['skipped_storage_save_count'],report['checkpoint_count'])
        self.assertEqual(self.proc_calls-before,report['checkpoint_count'])
        # Attempts, prompt IDs and completion all remain separately durable.
        self.assertEqual(len(saves),3)
        self.assertIn(row['name'],saves[0]['attempts']);self.assertNotIn(row['name'],saves[0]['completed'])
        self.assertTrue(saves[1]['prompt_ids']);self.assertIn(row['name'],saves[2]['completed'])

    def test_fast_storage_changes_still_save_and_never_reset_charged_bytes(self):
        row=self.ready_for_phase('timed-fast')
        initial=self.free
        def free_probe(_):
            self.free-=4096
            return self.free
        self.client.free_probe=free_probe
        self.execute(Transport(),row['name'])
        report=json.loads((self.root/'requests'/row['name']/'client-policy.json').read_text())
        self.assertEqual(report['skipped_storage_save_count'],0)
        self.assertEqual(report['storage_save_count'],report['checkpoint_count'])
        self.assertEqual(self.client.state['charged_write_bytes'],initial-self.free)

    def test_fast_keeps_fault_source_and_storage_checks(self):
        row=self.ready_for_phase('timed-fast')
        t=Transport(hook=lambda:(self.root/'FAULT.json').write_text('{}'))
        self.refused(t,row['name']);self.assertEqual(t.posts,1)
        self.assertNotIn(row['name'],self.client.state['completed'])
        self.assertFalse((self.root/'requests'/row['name']/'client-policy.json').exists())

    def test_fast_source_drift_is_checked_after_submit(self):
        row=self.ready_for_phase('timed-fast')
        t=Transport(hook=lambda:Path(self.contract['capture_guard_path']).write_text('# drift'))
        self.refused(t,row['name']);self.assertEqual(t.posts,1)
        self.assertNotIn(row['name'],self.client.state['completed'])

    def test_fast_disk_drawdown_is_checked_after_submit(self):
        row=self.ready_for_phase('timed-fast')
        def consume():self.free-=C.WRITE_ALLOWANCE+1
        t=Transport(hook=consume)
        self.refused(t,row['name']);self.assertEqual(t.posts,1)
        self.assertNotIn(row['name'],self.client.state['completed'])

    def test_policy_mismatch_refused_before_transport(self):
        row=self.ready_for_phase('timed-fast');row['client_checkpoint_policy']='always'
        t=Transport();self.refused(t,row['name']);self.assertEqual(t.posts,0)

    def test_failed_policy_receipt_cannot_durably_complete_request(self):
        original=C.write_new
        def fail(path,value):
            if path.name=='client-policy.json':raise OSError('synthetic readout fsync failure')
            return original(path,value)
        with patch.object(C,'write_new',side_effect=fail):self.refused(Transport())
        durable=json.loads((self.client_dir/'state.json').read_text())
        self.assertNotIn(self.name,durable['completed']);self.assertIsNotNone(durable['halted'])

    def test_attempt_limit_separate_from_capture_limit_and_contract_strict(self):
        for key, value in [('max_attempts',32),('max_attempts',29.0),('max_attempts',True),
                           ('max_attempts',None),('max_captures',71),('max_captures',22.0)]:
            original=self.contract[key]
            self.contract[key]=value
            with self.subTest(key=key,value=value),self.assertRaisesRegex(ValueError,'budget contract'):
                self.make_client()
            self.contract[key]=original

    def test_exhausted29_attempts_refuses_before_transport_or_output(self):
        self.client.acquire()
        try:
            self.client.state['attempts']=['prior-attempt-%d'%i for i in range(C.ATTEMPT_CAP)]
            self.client.save_state()
        finally:self.client.release()
        t=Transport()
        with self.assertRaisesRegex(ValueError,'attempt cap exhausted'):self.execute(t)
        self.assertEqual(t.posts,0)
        self.assertFalse((self.root/'requests'/self.name).exists())

    def test_full_schedule_does_not_advance_phase_from_completed_request_count(self):
        self.full_client()
        first_optimized=next(i for i,n in enumerate(self.client.ordered_names)
                             if self.client.rows[n]['phase']=='optimized-setup')
        for name in self.client.ordered_names[:first_optimized]:
            self.phase(self.client.rows[name]);self.execute(Transport(),name)
        name=self.client.ordered_names[first_optimized]
        self.phase(self.client.rows[name],phase='native_reference')
        t=Transport();self.refused(t,name);self.assertEqual(t.posts,0)

    def test_timing_needs_candidate_receipt_in_actual_phase_observation(self):
        self.full_client();self.client.acquire()
        first_timed = next(i for i,n in enumerate(self.client.ordered_names) if self.client.rows[n]['phase']=='timed-fast')
        try:
            self.client.state['completed']=self.client.ordered_names[:first_timed]
            self.client.state['attempts']=self.client.ordered_names[:first_timed];self.client.save_state()
        finally:self.client.release()
        name=self.client.ordered_names[first_timed];self.assertEqual(self.client.rows[name]['phase'],'timed-fast')
        self.phase(self.client.rows[name],candidate_receipt_sha256=None)
        t=Transport();self.refused(t,name);self.assertEqual(t.posts,0)

    def test_stale_phase_observation_refuses_before_setup_submit(self):
        self.full_client();name=self.client.ordered_names[0]
        self.phase(self.client.rows[name],observed_at_ms=1)
        t=Transport();self.refused(t,name);self.assertEqual(t.posts,0)

    def test_rehashed_modified_setup_schedule_not_admitted(self):
        self.full_client();p=Path(self.contract['setup_schedule_path']);value=json.loads(p.read_text())
        value['schedule']['rows'][0]['graph']['420']['inputs']['encoder_mode']='other'
        value['schedule_sha256']=C.G.sha(C.G.canonical(value['schedule']))
        self.write(p,value);self.contract['setup_schedule_sha256']=value['schedule_sha256']
        with self.assertRaisesRegex(ValueError,'Unreviewed setup schedule'):self.make_client()


if __name__=='__main__':unittest.main(verbosity=2)
