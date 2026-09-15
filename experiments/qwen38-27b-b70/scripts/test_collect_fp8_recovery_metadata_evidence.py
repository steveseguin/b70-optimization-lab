"""Synthetic CPU tests; never collect or inspect the active recovery campaign."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

PATH=Path(__file__).with_name('collect-fp8-recovery-metadata-evidence.py')
spec=importlib.util.spec_from_file_location('recovery_collect',PATH)
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)
IMAGE='sha256:7cd7bb16b1fd2e679f0230a38b2f0242fe1c278853867e697c0ce139be2133d2'
RESEARCH_IMAGE='sha256:506fcc26897b12915cb9e27c28e0adc256d278666fa745602a1ae5e1dd8ea066'


class RecoveryEvidence(unittest.TestCase):
    def test_closure_must_be_terminal_and_explicit(self):
        base={'status':'completed','finished_at':'2026-09-14T00:00:00Z','final_service':{'status':'ready'}}
        collector.closure_gate(base)
        for key,value in [('status','running'),('finished_at',''),('final_service',{})]:
            bad=copy.deepcopy(base);bad[key]=value
            with self.assertRaises(ValueError):collector.closure_gate(bad)
    def test_absent_service_is_not_ready(self):
        result=collector.final_service_gate({}, {}, {'status':'not-started'})
        self.assertFalse(result['ready_quality_verified'])
    def test_final_ready_requires_instance_binding(self):
        final={'status':'ready','source_dir':'recovered-service','strict_dir':'recovery-strict'}
        data={'raw/recovered-service/state.json':json.dumps({'status':'ready','image_id':IMAGE}).encode()}
        strict={'raw/recovery-strict':{'complete_12_prompt_qualification':True}}
        with self.assertRaises(ValueError):collector.final_service_gate(data,strict,final)
        final['binding_receipt']='missing-binding.json'
        with self.assertRaises(ValueError):collector.final_service_gate(data,strict,final)
    def test_final_ready_refuses_stopped_or_unknown_image(self):
        final={'status':'ready','source_dir':'final-service','strict_dir':'final-strict'}
        strict={'raw/final-strict':{'complete_12_prompt_qualification':True}}
        for status,image in [('stopped',IMAGE),('ready','unknown')]:
            data={'raw/final-service/state.json':json.dumps({'status':status,'image_id':image}).encode()}
            with self.assertRaises(ValueError):collector.final_service_gate(data,strict,final)
    def test_final_ready_does_not_accept_unregistered_directory(self):
        with self.assertRaises(ValueError):collector.final_service_gate({}, {}, {'status':'ready','source_dir':'elsewhere','strict_dir':'recovery-strict'})
    def parity_fixture(self):
        data={};origins={};report={'comparison':{'exact_prompts':1,'total_prompts':1,'complete_token_arrays_exact':True},'qualification':{'all_workload_and_canary_gates_passed':True,'strict_pair_qualified':True}}
        for side in ('left','right'):
            report[side]={'artifacts':{}}
            values={'performance':{'rows':[{'prompt_id':'p','prompt_sha256':'same-prompt','token_ids':[1,2]}],'realistic_final_gate':{'passed':True},'fresh_response_validity':{'valid':True,'cached_tokens_all_zero':True}},'canaries':{'pass_all':True},'identity':{'suite_sha256':'same-suite'}}
            for role,value in values.items():
                member=f'{side}/{role}.json';raw=json.dumps(value).encode();data[member]=raw
                origins[member]={'path':'/frozen/'+member}
                report[side]['artifacts'][role]={'path':'/frozen/'+member,'sha256':collector.sha(raw)}
        data['parity.json']=json.dumps(report).encode()
        return data,origins,report
    def test_parity_recomputed_from_full_arrays_and_hashes(self):
        data,origins,report=self.parity_fixture()
        self.assertEqual(collector.parity_replay(data,'parity.json',origins)['exact_prompts'],1)
        value=json.loads(data['right/performance.json']);value['rows'][0]['token_ids']=[1,3]
        data['right/performance.json']=json.dumps(value).encode()
        with self.assertRaises(ValueError):collector.parity_replay(data,'parity.json',origins)
        report['right']['artifacts']['performance']['sha256']=collector.sha(data['right/performance.json']);data['parity.json']=json.dumps(report).encode()
        with self.assertRaises(ValueError):collector.parity_replay(data,'parity.json',origins)
    def test_parity_quality_boolean_cannot_override_failed_canary(self):
        data,origins,report=self.parity_fixture()
        data['right/canaries.json']=b'{"pass_all":false}'
        report['right']['artifacts']['canaries']['sha256']=collector.sha(data['right/canaries.json']);data['parity.json']=json.dumps(report).encode()
        with self.assertRaises(ValueError):collector.parity_replay(data,'parity.json',origins)
    def test_archive_roundtrip_uses_frozen_helper(self):
        with tempfile.TemporaryDirectory() as tmp:
            data={'selection.json':b'{"synthetic":true}','point-in-time/closed/server.log':b'finished snapshot\n'}
            parts,members=collector.prior.build_archives(Path(tmp),data,{})
            loaded,binary=collector.prior.read_archives(Path(tmp),{'archives':parts,'members':members},temporary=True)
            self.assertEqual(loaded,data);self.assertEqual(binary,{})
    def test_health_phase_absent_is_not_run_and_unregistered_is_refused(self):
        self.assertEqual(collector.health_replay({},'health-after-research-oom'),{'phase':'health-after-research-oom','status':'not-run','passed_verified':False})
        with self.assertRaises(ValueError):collector.health_replay({},'health-elsewhere')
    def research_fixture(self):
        state={'status':'stop_unconfirmed','container_id':'c'*64,'container_name':'mtp-lossless-x','image_id':RESEARCH_IMAGE,'started_at':'2026-09-14T19:27:22.684375+00:00','boot_id':'boot'}
        raw={'raw/research-server/state.json':json.dumps(state).encode(),'raw/research-server/stop.json':b'{"stop_confirmed": false}','point-in-time/close/research-server/server.log':b'loading\n'}
        post={'schema':collector.RESEARCH_POSTFLIGHT_SCHEMA,'at':'2026-09-15T01:45:00+00:00','boot_id':'boot','same_boot_as_launch':True,
              'container':{'id':'c'*64,'name':'mtp-lossless-x','image':RESEARCH_IMAGE,'state':{'Running':False,'OOMKilled':True,'ExitCode':1,'FinishedAt':'2026-09-15T00:39:35.642978857Z'}},
              'exit_confirmed_by_later_inspection':True,'requests_served':0,'endpoint_ever_ready':False,
              'preserved_owner_receipts_sha256':{'state.json':collector.sha(raw['raw/research-server/state.json']),'stop.json':collector.sha(raw['raw/research-server/stop.json']),'server.log':collector.sha(raw['point-in-time/close/research-server/server.log'])},
              'gpu_fault_signature_lines':[],'xe_lines':['kernel: xe 0000:03:00.0: Using 46-bit DMA addresses'],
              'global_oom_kills':[{'pid':1}],'page_allocation_failures':[{'text':'failure'}],'last_allocation_failure_stack_kernel_clock':['ttm_bo_setup_export'],
              'first_oom_gib_outside_those_counters':12.65,'kernel_windows':{'launch_to_exit':{'sha256':'0'*64}}}
        return raw,post
    def test_research_postflight_binds_unchanged_owner_receipts(self):
        raw,post=self.research_fixture()
        data=dict(raw,**{'raw/research-server/postflight.json':json.dumps(post).encode()})
        result=collector.research_postflight_replay(data)
        self.assertTrue(result['exit_confirmed']);self.assertEqual(result['status'],'failed-during-load')
        changed=dict(data);changed['point-in-time/close/research-server/server.log']=b'rewritten\n'
        with self.assertRaises(ValueError):collector.research_postflight_replay(changed)
        mutations=(lambda p:p['container']['state'].update(Running=True),
                   lambda p:p.update(gpu_fault_signature_lines=['xe 0000:03:00.0: [drm] Fault response: Unsuccessful']),
                   lambda p:p.update(requests_served=1),
                   lambda p:p['container'].update(id='d'*64))
        for mutate in mutations:
            bad=copy.deepcopy(post);mutate(bad)
            with self.assertRaises(ValueError):collector.research_postflight_replay(dict(raw,**{'raw/research-server/postflight.json':json.dumps(bad).encode()}))
    def test_research_without_postflight_does_not_claim_exit(self):
        raw,_=self.research_fixture()
        self.assertEqual(collector.research_postflight_replay(raw),{'status':'stop_unconfirmed','exit_confirmed':False})
        self.assertEqual(collector.research_postflight_replay({}),{'status':'not-run','exit_confirmed':False})
    def test_ready_after_failed_research_requires_later_health(self):
        ready={'ready_quality_verified':True};first={'passed_verified':True}
        research={'status':'failed-during-load','exit_confirmed':True,'finished_at':'2026-09-15T00:39:35.642978857Z'}
        later={'phase':'health-after-research-oom','passed_verified':True,'started_at':'2026-09-15T01:58:17+00:00','finished_at':'2026-09-15T01:58:27+00:00'}
        result=collector.ready_health_gate(ready,{'health':first,'health-after-research-oom':later},research,'2026-09-15T01:58:47+00:00')
        self.assertTrue(result['post_incident_health_required'])
        missing={'phase':'health-after-research-oom','status':'not-run','passed_verified':False}
        cases=[({'health':first,'health-after-research-oom':missing},research,'2026-09-15T01:58:47+00:00'),
               ({'health':first,'health-after-research-oom':dict(later,started_at='2026-09-15T00:30:00+00:00')},research,'2026-09-15T01:58:47+00:00'),
               ({'health':first,'health-after-research-oom':later},research,'2026-09-15T01:58:20+00:00'),
               ({'health':first,'health-after-research-oom':later},dict(research,exit_confirmed=False),'2026-09-15T01:58:47+00:00'),
               ({'health':{'passed_verified':False},'health-after-research-oom':later},research,'2026-09-15T01:58:47+00:00')]
        for healths,stage,started in cases:
            with self.assertRaises(ValueError):collector.ready_health_gate(ready,healths,stage,started)
        self.assertFalse(collector.ready_health_gate(ready,{'health':first},{'status':'not-run','exit_confirmed':False})['post_incident_health_required'])
        self.assertEqual(collector.ready_health_gate({'ready_quality_verified':False},{},research),{'ready_claim':False})

if __name__=='__main__':unittest.main()
