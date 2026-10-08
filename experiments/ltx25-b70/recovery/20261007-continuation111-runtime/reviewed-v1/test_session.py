"""Synthetic authority tests; no models, captures, device imports or endpoints."""
import copy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import session as s

PLAN = Path(__file__).resolve().parent.parent/'20261007-continuation111-plan/candidate-plan.json'


def state():
    return {'fault': False, 'queue_running': 0, 'queue_pending': 0,
            'pipeline': {'running': 0, 'stages': {}}, 'preview_pending': 0,
            'preview_failures': 0, 'sampler_routes': 0, 'lean_state': 0,
            'decode_replicas': 0, 'captures_frozen': False, 'loads_frozen': False}


class AuthorityTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.run = Path(self.temp.name)
        self.observed = state()
        self.calls = []
        self.a = s.Authority(PLAN, '1'*64, '2'*64, self.run,
                             lambda: copy.deepcopy(self.observed), self.verify)
        self.names = list(self.a.order)

    def verify(self, name, path, sha):
        self.calls.append(name)
        value = s.strict_json(s.read_regular(path))
        if value.pop('proof_check') != 'synthetic-check-passed':
            raise RuntimeError('Independent verifier refused')
        return value

    def start(self, index):
        name = self.names[index]
        return self.a.begin(name, copy.deepcopy(self.a.requests[name]['graph']), 'pid-'+str(index))

    def finish(self, index):
        self.a.finish([('execution_start', {'prompt_id': 'pid-'+str(index)}),
                       ('execution_success', {'prompt_id': 'pid-'+str(index)})])

    def proof_file(self, index, **updates):
        name = self.names[index]
        value = {'plan_sha256': s.PLAN_SHA256, 'runtime_manifest_sha256': '1'*64,
                 'server_identity_sha256': '2'*64, 'name': name,
                 'prompt_id': 'pid-'+str(index), 'verified': True,
                 'proof_check': 'synthetic-check-passed', 'tensor_hashes': ['3'*64]*4}
        value.update(updates)
        path = self.run/('continuation-proof-'+name+'.json')
        s.write_exclusive(path, value)
        return path, s.digest(path.read_bytes())

    def accept(self, index):
        path, sha = self.proof_file(index)
        return self.a.accept_proof(self.names[index], path, sha)

    def complete(self, index):
        self.start(index); self.finish(index); self.accept(index)

    def test_full_eight_sequence_six_captures_and_no_phase_advance(self):
        for index in range(8):
            row = self.start(index)
            self.assertEqual(row['name'], self.names[index])
            self.assertEqual(self.a.require_phase('native', s.QUALIFICATION_ID, row['name'])['phase'],
                             'native_reference')
            if index in (3, 4, 6, 7):
                previous = row['predecessor_capture']
                self.assertEqual(self.a.revalidate_proof(previous)['checked']['name'], previous)
            self.finish(index)
            self.assertNotIn(row['name'], self.a.proofs)
            self.accept(index)
        self.assertEqual(self.a.completed, self.names)
        self.assertEqual(len(self.a.proofs), 8)
        self.assertEqual(self.a.capture_count, 6)
        self.assertEqual(self.a.phase, 'native_reference')
        self.assertIsNone(self.a.active)
        self.assertEqual(self.a.barriers['first-conditioned-verified'], self.names[3])
        self.assertGreater(self.calls.count(self.names[3]), 1)
        self.assertEqual(len(list(self.run.glob('continuation-proof-accepted-*.json'))), 8)

    def test_global_order_refuses_skip_to_native(self):
        with self.assertRaisesRegex(RuntimeError, 'Global request order'):
            self.start(2)
        self.assertIsNotNone(self.a.failed)
        self.assertEqual(self.a.capture_count, 0)

    def test_execution_success_alone_does_not_unlock_next(self):
        self.start(0); self.finish(0)
        with self.assertRaisesRegex(RuntimeError, 'Proof not accepted'):
            self.start(1)
        self.assertEqual(self.a.completed, self.names[:1])

    def test_proof_for_active_or_uncompleted_request_refused(self):
        path, sha = self.proof_file(0)
        with self.assertRaisesRegex(RuntimeError, 'next completed'):
            self.a.accept_proof(self.names[0], path, sha)
        self.assertEqual(self.calls, [])

    def test_actual_prompt_ledger_not_proof_claim(self):
        self.start(0); self.finish(0)
        path, sha = self.proof_file(0, prompt_id='invented')
        with self.assertRaisesRegex(RuntimeError, 'identity/verdict'):
            self.a.accept_proof(self.names[0], path, sha)
        self.assertEqual(self.a.proofs, {})

    def test_independent_callback_required_even_matching_json(self):
        self.start(0); self.finish(0)
        path, sha = self.proof_file(0, proof_check='bad')
        with self.assertRaisesRegex(RuntimeError, 'Independent verifier'):
            self.a.accept_proof(self.names[0], path, sha)
        self.assertEqual(self.a.proofs, {})

    def test_wrong_identity_and_nonboolean_verdict_refused(self):
        for field, value in [('plan_sha256', '9'*64), ('runtime_manifest_sha256', '9'*64),
                             ('server_identity_sha256', '9'*64), ('name', 'different'),
                             ('verified', 1), ('verified', False)]:
            with self.subTest(field=field, value=value):
                with tempfile.TemporaryDirectory() as directory:
                    run = Path(directory)
                    a = s.Authority(PLAN, '1'*64, '2'*64, run, state,
                                    lambda n,p,h: {**base, field:value})
                    name = a.order[0]
                    base = {'plan_sha256':s.PLAN_SHA256,'runtime_manifest_sha256':'1'*64,
                            'server_identity_sha256':'2'*64,'name':name,'prompt_id':'pid','verified':True}
                    a.begin(name, a.requests[name]['graph'], 'pid')
                    a.finish([('execution_success',{'prompt_id':'pid'})])
                    path=run/('continuation-proof-'+name+'.json');s.write_exclusive(path,{})
                    with self.assertRaises(RuntimeError):a.accept_proof(name,path,s.digest(path.read_bytes()))
                    self.assertEqual(a.proofs,{})

    def test_changed_proof_file_refuses_next_before_request(self):
        self.complete(0)
        path=Path(self.a.proofs[self.names[0]]['path']);path.write_bytes(b'{}')
        with self.assertRaisesRegex(RuntimeError, 'Proof file changed'):
            self.start(1)
        self.assertFalse((self.run/('resolution-before-'+self.names[1]+'.json')).exists())

    def test_callback_changed_result_refuses_same_file(self):
        self.complete(0)
        original=self.a.verify_proof
        self.a.verify_proof=lambda n,p,h: {**original(n,p,h), 'tensor_hashes':['4'*64]*4}
        with self.assertRaisesRegex(RuntimeError,'proof result changed'):
            self.start(1)

    def test_callback_file_mutation_refused(self):
        self.start(0);self.finish(0);path,sha=self.proof_file(0)
        original=self.a.verify_proof
        def change(n,p,h):
            result=original(n,p,h);p.write_bytes(b'{}');return result
        self.a.verify_proof=change
        with self.assertRaisesRegex(RuntimeError,'changed during verification'):
            self.a.accept_proof(self.names[0],path,sha)
        self.assertEqual(self.a.proofs,{})

    def test_missing_fixed_path_or_alias_refused(self):
        self.start(0);self.finish(0)
        with self.assertRaises(FileNotFoundError):
            self.a.accept_proof(self.names[0],self.run/('continuation-proof-'+self.names[0]+'.json'),'3'*64)
        self.assertEqual(self.calls,[])

    def test_wrong_path_refused_without_callback(self):
        self.start(0);self.finish(0)
        path=self.run/'arbitrary.json';s.write_exclusive(path,{})
        with self.assertRaisesRegex(RuntimeError,'path is not fixed'):
            self.a.accept_proof(self.names[0],path,s.digest(path.read_bytes()))
        self.assertEqual(self.calls,[])

    def test_rehashed_graph_and_mutated_registered_plan_refused(self):
        graph=copy.deepcopy(self.a.requests[self.names[0]]['graph'])
        graph['420']['inputs']['placement']='other'
        with self.assertRaisesRegex(RuntimeError,'Submitted graph differs'):
            self.a.begin(self.names[0],graph,'pid')
        other=s.Authority(PLAN,'1'*64,'2'*64,self.run,state,self.verify)
        other.requests[self.names[0]]['graph']['420']['inputs']['placement']='other'
        with self.assertRaisesRegex(RuntimeError,'plan/phase changed'):
            other.begin(self.names[0],other.requests[self.names[0]]['graph'],'pid')

    def test_returned_row_is_not_mutable_authority_alias(self):
        row=self.start(0);row['graph']['420']['inputs']['placement']='other'
        self.a.healthy()
        self.assertEqual(self.a.requests[self.names[0]]['graph']['420']['inputs']['placement'],'split')

    def test_reused_prompt_and_ninth_request_refused(self):
        self.complete(0)
        with self.assertRaisesRegex(RuntimeError,'reused prompt'):
            self.a.begin(self.names[1],self.a.requests[self.names[1]]['graph'],'pid-0')

    def test_ninth_request_refused_after_all_proofs(self):
        for i in range(8):self.complete(i)
        with self.assertRaisesRegex(RuntimeError,'exhausted'):
            self.a.begin(self.names[0],self.a.requests[self.names[0]]['graph'],'new')
        self.assertEqual(self.a.capture_count,6)

    def test_seventh_capture_reservation_refused_independently_of_request_order(self):
        self.complete(0);self.complete(1)
        self.a.capture_count=6
        with self.assertRaisesRegex(RuntimeError,'Six-capture allowance'):
            self.start(2)
        self.assertEqual(self.a.capture_count,6)
        self.assertIsNone(self.a.active)

    def test_reaccepting_proof_or_mutating_returned_binding(self):
        self.start(0);self.finish(0)
        result=self.accept(0)
        result['checked']['prompt_id']='changed'
        self.assertEqual(self.a.proofs[self.names[0]]['checked']['prompt_id'],'pid-0')
        with self.assertRaisesRegex(RuntimeError,'next completed'):
            self.a.accept_proof(self.names[0],result['path'],result['sha256'])

    def test_callback_nonfinite_result_and_incomplete_observation_refused(self):
        self.start(0);self.finish(0);path,sha=self.proof_file(0)
        original=self.a.verify_proof
        self.a.verify_proof=lambda n,p,h: {**original(n,p,h),'bad':float('inf')}
        with self.assertRaises(ValueError):self.a.accept_proof(self.names[0],path,sha)
        self.assertEqual(self.a.proofs,{})
        with tempfile.TemporaryDirectory() as d:
            observed=state();del observed['preview_pending']
            a=s.Authority(PLAN,'1'*64,'2'*64,Path(d),lambda:observed,self.verify)
            with self.assertRaisesRegex(RuntimeError,'Incomplete native observation'):
                a.begin(a.order[0],a.requests[a.order[0]]['graph'],'pid')

    def test_fault_optimized_or_busy_state_refuses(self):
        changes=[{'fault':True},{'sampler_routes':1},{'lean_state':1},{'decode_replicas':1},
                 {'captures_frozen':True},{'queue_pending':1},{'queue_running':2},
                 {'preview_pending':1},{'preview_failures':1},
                 {'pipeline':{'running':1,'stages':{}}},
                 {'pipeline':{'running':0,'stages':{'sample':{'queued_indices':[],
                    'jobs':[{'done':True,'error':None}]}}}}]
        for delta in changes:
            with self.subTest(delta=delta),tempfile.TemporaryDirectory() as d:
                observed={**state(),**delta};a=s.Authority(PLAN,'1'*64,'2'*64,Path(d),lambda:observed,self.verify)
                with self.assertRaises(RuntimeError):a.begin(a.order[0],a.requests[a.order[0]]['graph'],'pid')
                self.assertIsNotNone(a.failed)

    def test_current_prompt_may_be_counted_but_idle_proof_may_not(self):
        self.observed['queue_running']=1
        self.start(0);self.finish(0)
        path,sha=self.proof_file(0)
        with self.assertRaisesRegex(RuntimeError,'queue is not empty'):
            self.a.accept_proof(self.names[0],path,sha)

    def test_cached_interrupted_or_duplicate_success_refused(self):
        for extra in [('execution_cached',{'nodes':['420']}),('execution_interrupted',{}),
                      ('execution_error',{}),('execution_success',{'prompt_id':'pid'})]:
            with self.subTest(extra=extra),tempfile.TemporaryDirectory() as d:
                a=s.Authority(PLAN,'1'*64,'2'*64,Path(d),state,self.verify)
                a.begin(a.order[0],a.requests[a.order[0]]['graph'],'pid')
                with self.assertRaises(RuntimeError):
                    a.finish([('execution_success',{'prompt_id':'pid'}),extra])
                self.assertEqual(a.completed,[])

    def test_durable_write_failure_latches_before_any_retry(self):
        with patch.object(s,'write_exclusive',side_effect=OSError('disk full')):
            with self.assertRaisesRegex(OSError,'disk full'):self.start(0)
        self.assertIsNotNone(self.a.failed)
        self.assertIn('disk full',self.a.halt_receipt_error)
        with self.assertRaisesRegex(RuntimeError,'Session halted'):self.start(0)

    def test_finish_write_failure_does_not_complete(self):
        self.start(0)
        with patch.object(s,'write_exclusive',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.finish(0)
        self.assertEqual(self.a.completed,[])
        self.assertIsNotNone(self.a.active)

    def test_accept_write_failure_does_not_publish_proof(self):
        self.start(0);self.finish(0);path,sha=self.proof_file(0)
        with patch.object(s,'write_exclusive',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.a.accept_proof(self.names[0],path,sha)
        self.assertEqual(self.a.proofs,{})
        self.assertEqual(self.a.barriers,{})

    def test_reentrant_callback_cannot_swallow_refusal(self):
        self.start(0);self.finish(0);path,sha=self.proof_file(0)
        original=self.a.verify_proof
        def reenter(n,p,h):
            try:self.a.revalidate_proof(n)
            except RuntimeError:pass
            return original(n,p,h)
        self.a.verify_proof=reenter
        with self.assertRaisesRegex(RuntimeError,'Session halted'):
            self.a.accept_proof(self.names[0],path,sha)
        self.assertEqual(self.a.proofs,{})
        self.assertIsNone(self.a._busy)

    def test_phase_alias_and_auxiliary_module_contract(self):
        with patch.object(s,'_authority',self.a):
            self.start(0)
            auth=s.require_phase('text',s.QUALIFICATION_ID,self.names[0])
            self.assertEqual(auth['comparison_mode'],'same-size-native-v1')
            self.assertEqual(s.auxiliary_metadata()['output_parity_claimed'],False)
            with self.assertRaisesRegex(RuntimeError,'refuses role'):
                s.require_phase('sampler',s.QUALIFICATION_ID,self.names[0])
            self.assertTrue(s.auxiliary_metadata()['halted'])

    def test_file_safety_and_strict_json(self):
        for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b'{"x":1e999}'):
            with self.assertRaises((RuntimeError,ValueError)):s.strict_json(raw)
        regular=self.run/'regular';regular.write_bytes(b'{}')
        link=self.run/'link';link.symlink_to(regular)
        with self.assertRaises(RuntimeError):s.read_regular(link)
        link.unlink();os.link(regular,link)
        with self.assertRaises(RuntimeError):s.read_regular(regular)
        fifo=self.run/'fifo';os.mkfifo(fifo)
        with self.assertRaises(RuntimeError):s.read_regular(fifo)

    def test_rehashed_plan_not_admitted(self):
        value=json.loads(PLAN.read_bytes());value['plan']['budget']['max_captures']=7
        value['plan_sha256']=s.digest(s.canonical(value['plan']))
        path=self.run/'plan.json';s.write_exclusive(path,value)
        with self.assertRaisesRegex(RuntimeError,'fixed reviewed'):
            s.Authority(path,'1'*64,'2'*64,self.run,state,self.verify)


if __name__=='__main__':unittest.main()
