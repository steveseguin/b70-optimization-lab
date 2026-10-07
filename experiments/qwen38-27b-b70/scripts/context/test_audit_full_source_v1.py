"""CPU evidence tests; fake exchange never opens a network connection."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import audit_full_source_v1 as audit

spec=importlib.util.spec_from_file_location('_audit_full_source_fixture_client',audit.HERE/'full_source_v1/client.py')
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
        self.packet=self.root/'packet';self.bundle=client.prepare(self.packet);self.output=self.root/'out'
        self.identity=self.root/'identity.json';self.identity.write_text('{"cpu_fake_launch":true}')

    def envelope(self,index=0,content=None,finish='stop',usage='default',model=audit.MODEL):
        task=self.bundle['tasks'][audit.ORDER[index]]
        if content is None:content=json.dumps({'action':'submit','answers':task['oracle']['answers']})
        value={'model':model,'choices':[{'finish_reason':finish,'message':{'role':'assistant','content':content,'reasoning':'retained fixture reasoning'}}]}
        if usage=='default':usage={'prompt_tokens':3300,'completion_tokens':400,'total_tokens':3700,
                'prompt_tokens_details':{'cached_tokens':0},'completion_tokens_details':{'reasoning_tokens':300}}
        if usage is not None:value['usage']=usage
        return audit.encoded(value)

    def run_model(self,first=None,second=None,transport=None,expect_error=False):
        values=iter([first or self.envelope(0),second or self.envelope(1)])
        def exchange(*args):return next(values),copy.deepcopy(transport or {'http_status':200,'headers':{},'error':None,'raw_truncated':False})
        with patch.object(client,'exchange',side_effect=exchange):
            if expect_error:
                with self.assertRaises(Exception):client.execute(self.packet,self.output,'http://127.0.0.1:18196/v1',identity=self.identity)
            else:client.execute(self.packet,self.output,'http://127.0.0.1:18196/v1',identity=self.identity)
        return audit.audit(self.output,self.packet)

    def rebind(self,index=0):
        case=audit.ORDER[index];directory=self.output/case;result=audit.read(directory/'result.json')
        for name,record in result['artifacts'].items():record.update(sha256=audit.sha(directory/name),bytes=(directory/name).stat().st_size)
        client.save(directory/'result.json',result)
        timing=audit.read(directory/'timing.json');timing['result_sha256']=audit.sha(directory/'result.json');client.save(directory/'timing.json',timing)
        summary=audit.read(self.output/'summary.json');summary['trials'][index].update(result_sha256=audit.sha(directory/'result.json'),timing_sha256=audit.sha(directory/'timing.json'));client.save(self.output/'summary.json',summary)

    def test_real_client_stub_and_model_fixtures(self):
        client.execute(self.packet,self.output,stub=True);result=audit.audit(self.output,self.packet)
        self.assertEqual(result['completed_trials'],2)
        for row in result['trials']:
            self.assertEqual(row['score']['correct'],24);self.assertFalse(row['final_task_success']);self.assertFalse(row['cost_eligible'])
            self.assertIsNone(row['checkpoint_quality']);self.assertIsNone(row['event_quality'])
        shutil.rmtree(self.output);result=self.run_model()
        self.assertTrue(all(r['final_task_success'] and r['cost_eligible'] for r in result['trials']))

    def test_portable_without_tokenizer_or_client_runtime_import(self):
        client.execute(self.packet,self.output,stub=True)
        # Audit imports only the pinned compiler; host tokenizer/client validator
        # are not dependencies for replaying preserved records.
        original_open=Path.open
        def offline_open(path,*args,**kwargs):
            if str(path).startswith('/mnt/'):raise AssertionError('host tokenizer/model paths forbidden in audit')
            return original_open(path,*args,**kwargs)
        with patch.object(client,'validate_packet',side_effect=AssertionError('client validator not allowed')),patch.object(Path,'open',offline_open):
            result=audit.audit(self.output,self.packet)
        self.assertEqual(result['planned_trials'],2)
        self.assertNotIn('tokenizers',audit.__dict__)

    def test_rebound_request_cannot_change_source_question_or_generation(self):
        self.run_model();path=self.output/audit.ORDER[0]/'request.json';original=path.read_bytes()
        for change in ('source','question','temperature'):
            with self.subTest(change=change):
                request=json.loads(original)
                if change=='temperature':request['temperature']=1
                else:
                    public=json.loads(request['messages'][1]['content']);key='batches' if change=='source' else 'questions'
                    public[key][0]['text']='tampered';request['messages'][1]['content']=json.dumps(public,ensure_ascii=False)
                path.write_bytes(audit.encoded(request));self.rebind()
                with self.assertRaises(ValueError):audit.audit(self.output,self.packet)
                path.write_bytes(original);self.rebind()

    def test_private_reference_tamper_rejected_even_rebound(self):
        self.run_model();taskfile=self.packet/(audit.ORDER[0]+'-task.json');task=audit.read(taskfile)
        task['oracle']['answers'][next(iter(task['oracle']['answers']))]+=1;client.save(taskfile,task)
        plan=audit.read(self.packet/'plan.json');plan['files_sha256'][taskfile.name]=audit.sha(taskfile);client.save(self.packet/'plan.json',plan)
        with self.assertRaises(ValueError):audit.audit(self.output,self.packet)

    def test_source_annotation_and_candidate_hardpins(self):
        for relative in ('source/documents.json','source/annotations-review.json','feasibility.json'):
            with self.subTest(relative=relative):
                path=self.packet/relative;raw=path.read_bytes();path.write_bytes(raw+b' ')
                with self.assertRaises(ValueError):audit.load_packet(self.packet)
                path.write_bytes(raw)

    def test_forged_success_and_score_rejected_after_hash_rebinding(self):
        self.run_model();path=self.output/audit.ORDER[0]/'result.json';original=path.read_bytes()
        for key in ('score','success','checkpoints'):
            with self.subTest(key=key):
                value=json.loads(original)
                if key=='score':value['response']['score']['correct']=23
                elif key=='success':value['final_task_success']=False
                else:value['checkpoint_quality']=True
                client.save(path,value);self.rebind()
                with self.assertRaises(ValueError):audit.audit(self.output,self.packet)
                path.write_bytes(original);self.rebind()

    def test_capped_response_preserves_raw_score_but_fails(self):
        result=self.run_model(first=self.envelope(finish='length'))
        self.assertEqual(result['failed_trials'],1);row=result['trials'][0]
        self.assertEqual(row['score']['correct'],24);self.assertFalse(row['final_task_success']);self.assertFalse(row['cost_eligible'])
        self.assertEqual(result['trials'][1]['status'],'completed')

    def test_bad_format_extra_ids_types_and_duplicate_keys(self):
        gold=self.bundle['tasks'][audit.ORDER[0]]['oracle']['answers'];qid=next(iter(gold))
        variants=[('malformed','{'),('duplicate','{"action":"submit","answers":'+json.dumps(gold)[:-1]+',"'+qid+'":0}}')]
        for label,mutator in [('extra-id',lambda x:x.update(extra=1)),('wrong-type',lambda x:x.update({qid:True})),('missing',lambda x:x.pop(qid))]:
            answers=copy.deepcopy(gold);mutator(answers);variants.append((label,json.dumps({'action':'submit','answers':answers})))
        variants.append(('extra-top',json.dumps({'action':'submit','answers':gold,'extra':True})))
        for label,content in variants:
            with self.subTest(label=label):
                result=self.run_model(first=self.envelope(content=content));self.assertEqual(result['failed_trials'],1)
                self.assertFalse(result['trials'][0]['final_task_success']);shutil.rmtree(self.output)

    def test_null_and_wrong_integer_are_completed_wrong_answers(self):
        gold=self.bundle['tasks'][audit.ORDER[0]]['oracle']['answers'];qid=next(iter(gold))
        for value in (None,gold[qid]+1):
            answers={**gold,qid:value};result=self.run_model(first=self.envelope(content=json.dumps({'action':'submit','answers':answers})))
            self.assertEqual(result['completed_trials'],2);self.assertEqual(result['trials'][0]['score']['correct'],23)
            self.assertFalse(result['trials'][0]['final_task_success']);shutil.rmtree(self.output)

    def test_unknown_nonzero_and_invalid_usage_leave_accuracy_intact(self):
        good=json.loads(self.envelope())['usage']
        variants=[None,{**good,'prompt_tokens_details':{'cached_tokens':1}},
                  {**good,'prompt_tokens_details':{'cached_tokens':True}},
                  {**good,'prompt_tokens_details':{'cached_tokens':3301}},
                  {**good,'completion_tokens':-1},{**good,'total_tokens':3699},
                  {**good,'completion_tokens_details':{'reasoning_tokens':401}}]
        for usage in variants:
            with self.subTest(usage=usage):
                result=self.run_model(first=self.envelope(usage=usage));row=result['trials'][0]
                self.assertTrue(row['final_task_success']);self.assertFalse(row['cost_eligible']);shutil.rmtree(self.output)

    def test_native_cache_metadata_cannot_diverge_from_raw(self):
        self.run_model();path=self.output/audit.ORDER[0]/'result.json';value=audit.read(path)
        value['response']['cache_usage']['cached_tokens']=1;client.save(path,value);self.rebind()
        with self.assertRaises(ValueError):audit.audit(self.output,self.packet)

    def test_infrastructure_envelope_and_wrong_returned_model_stop_remaining(self):
        for raw in (b'{bad HTTP JSON',self.envelope(model='wrong-model')):
            result=self.run_model(first=raw,expect_error=True)
            self.assertTrue(result['infrastructure_abort']);self.assertEqual(result['failed_trials'],1);self.assertEqual(result['unstarted_trials'],1)
            self.assertEqual(result['trials'][0]['failure_kind'],'infrastructure');shutil.rmtree(self.output)

    def test_missing_completed_row_and_reordered_summary_rejected(self):
        self.run_model();summarypath=self.output/'summary.json';summary=audit.read(summarypath)
        summary['trials'].reverse();client.save(summarypath,summary)
        with self.assertRaises(ValueError):audit.audit(self.output,self.packet)
        summary['trials'].reverse();client.save(summarypath,summary)
        (self.output/audit.ORDER[0]/'result.json').unlink()
        with self.assertRaises(ValueError):audit.audit(self.output,self.packet)

    def test_partial_infrastructure_manifest_preserved(self):
        with patch.object(client,'write',side_effect=OSError('fixture write failure')):
            with self.assertRaises(OSError):client.execute(self.packet,self.output,stub=True)
        # Initial summary write itself failed; build an explicit retained partial
        # manifest from the fixed plan, never invent a completed request.
        summary={'schema':'full-source-summary.v1','protocol':audit.PROTOCOL,'measurement_kind':'stub','expected_trials':2,
            'infrastructure_abort':True,'error':'fixture write failure','server_identity':None,
            'trials':[{**r,'status':'incomplete' if i==0 else 'unstarted'} for i,r in enumerate(self.bundle['plan']['trials'])],
            'completed_trials':0,'failed_trials':0,'unstarted_trials':[audit.ORDER[1]],
            'source_code_sha256':self.bundle['plan']['source_code_sha256'],'plan_sha256':audit.sha(self.packet/'plan.json'),
            'checkpoint_quality':None,'event_quality':None,'speed_gate_passed':False,'holdout_admitted':False}
        client.save(self.output/'summary.json',summary);result=audit.audit(self.output,self.packet)
        self.assertEqual(result['incomplete_trials'],1);self.assertEqual(result['unstarted_trials'],1)

    def test_partial_durable_result_without_timing_stays_incomplete(self):
        self.run_model()
        shutil.rmtree(self.output/audit.ORDER[1])
        (self.output/audit.ORDER[0]/'timing.json').unlink()
        summary=audit.read(self.output/'summary.json')
        summary.update(completed_trials=0,failed_trials=0,infrastructure_abort=True,error='timing persistence failure',unstarted_trials=[audit.ORDER[1]])
        summary['trials']=[{**r,'status':'incomplete' if i==0 else 'unstarted'} for i,r in enumerate(self.bundle['plan']['trials'])]
        client.save(self.output/'summary.json',summary)
        result=audit.audit(self.output,self.packet)
        self.assertEqual(result['incomplete_trials'],1)
        self.assertIn('result_sha256',result['trials'][0])
        self.assertNotIn('final_task_success',result['trials'][0])

    def test_infrastructure_cannot_be_reclassified_as_model_failure(self):
        result=self.run_model(first=b'not an API envelope',expect_error=True)
        path=self.output/audit.ORDER[0]/'result.json';value=audit.read(path)
        value['failure_kind']='model_or_protocol';client.save(path,value);self.rebind()
        with self.assertRaises(ValueError):audit.audit(self.output,self.packet)

    def test_stub_cannot_claim_model_success_or_cold_cost(self):
        client.execute(self.packet,self.output,stub=True)
        path=self.output/audit.ORDER[0]/'result.json';value=audit.read(path)
        value['final_task_success']=True;value['cold_cost_interpretation']=True
        client.save(path,value);self.rebind()
        with self.assertRaises(ValueError):audit.audit(self.output,self.packet)

    def test_rebound_cost_must_remain_finite_and_match_result(self):
        self.run_model();path=self.output/audit.ORDER[0]/'timing.json';timing=audit.read(path)
        timing['request_seconds']+=1;client.save(path,timing)
        summary=audit.read(self.output/'summary.json');summary['trials'][0]['timing_sha256']=audit.sha(path);client.save(self.output/'summary.json',summary)
        with self.assertRaises(ValueError):audit.audit(self.output,self.packet)


if __name__=='__main__':unittest.main()
