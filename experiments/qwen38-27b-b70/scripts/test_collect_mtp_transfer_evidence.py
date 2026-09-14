"""CPU-only archive integrity tests with temporary synthetic bytes."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import types

PATH=Path(__file__).with_name('collect-mtp-transfer-evidence.py')
spec=importlib.util.spec_from_file_location('mtp_collector',PATH)
collector=importlib.util.module_from_spec(spec);spec.loader.exec_module(collector)


class EvidenceArchive(unittest.TestCase):
    def test_unsafe_member_names_refused(self):
        for name in ('/absolute','../escape','a/../../escape','.'):
            with self.assertRaises(ValueError):collector.safe_relative(name)
    def test_symlink_input_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)/'real';target.write_bytes(b'data')
            link=Path(tmp)/'link';link.symlink_to(target)
            with self.assertRaises(ValueError):collector.hash_file(link)
    def test_streamed_roundtrip_and_operator_bits(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);binary=root/'fixture.bin';binary.write_bytes(bytes(range(256))*16)
            name='operator-output-bits/'+collector.sha(binary.read_bytes())+'.bin'
            data={'test.json':b'{"checked":true}\n'}
            parts,members=collector.build_archives(root,data,{name:binary})
            parsed,bits=collector.read_archives(root,{'archives':parts,'members':members},temporary=True)
            self.assertEqual(parsed,data);self.assertEqual(bits[name]['bytes'],4096)
            self.assertEqual(bits[name]['sha256'],collector.sha(binary.read_bytes()))
    def test_archive_and_member_corruption_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);parts,members=collector.build_archives(root,{'test.json':b'{"x":1}'},{})
            modified=copy.deepcopy(members);modified['test.json']['sha256']='0'*64
            with self.assertRaises(ValueError):collector.read_archives(root,{'archives':parts,'members':modified},temporary=True)
            archive=root/(parts[0]['name']+'.tmp');archive.write_bytes(archive.read_bytes()+b'corrupt')
            with self.assertRaises(ValueError):collector.read_archives(root,{'archives':parts,'members':members},temporary=True)
    def test_archive_parts_are_deterministic(self):
        with tempfile.TemporaryDirectory() as first,tempfile.TemporaryDirectory() as second:
            data={'one.json':b'{"x":1}','two.txt':b'fixed evidence'}
            a,_=collector.build_archives(Path(first),data,{})
            b,_=collector.build_archives(Path(second),data,{})
            self.assertEqual(a,b)
    def test_strict_timing_recomputed_and_mismatch_retained(self):
        rows=[]
        for i in range(12):
            rows.append({'prompt_id':str(i),'prompt_sha256':str(i),'prompt_class':'class-'+str(i%3),'token_ids':list(range(100)),'completion_tokens':100,'cached_tokens':0,'token_id_offsets_s':[x/50 for x in range(100)],'tok_s_1_100_intervals_after_ttft':50.0})
        performance={'rows':rows,'summary':{'class_balanced_tok_s_1_100_intervals_after_ttft':{'median':50.0}},'realistic_final_gate':{'passed':True}}
        data={'fixture/performance.json':json.dumps(performance).encode(),'fixture/canaries.json':b'{"pass_all":true}'}
        result,reference=collector.strict_replay(data,'fixture')
        self.assertTrue(result['complete_12_prompt_qualification'])
        wrong=copy.deepcopy(reference);wrong['0']['token_ids'][0]=999
        result,_=collector.strict_replay(data,'fixture',wrong)
        self.assertFalse(result['complete_outputs_match_frozen'])
        performance['rows'][0]['tok_s_1_100_intervals_after_ttft']=51
        data['fixture/performance.json']=json.dumps(performance).encode()
        with self.assertRaises(ValueError):collector.strict_replay(data,'fixture')

    def test_short_strict_event_arrays_never_qualify(self):
        row={'prompt_id':'0','prompt_sha256':'0','prompt_class':'prose','token_ids':list(range(100)),
             'completion_tokens':100,'cached_tokens':0,'token_id_offsets_s':[],
             'tok_s_1_100_intervals_after_ttft':None}
        rows=[dict(row,prompt_id=str(i)) for i in range(12)]
        p={'rows':rows,'summary':{},'realistic_final_gate':{'passed':True}}
        data={'p/performance.json':json.dumps(p).encode(),'p/canaries.json':b'{"pass_all":true}'}
        result,_=collector.strict_replay(data,'p')
        self.assertFalse(result['complete_12_prompt_qualification'])

    def test_complete_rpc_replay_rejects_counter_and_source_drift(self):
        client=collector.load_module('test_replay_client',PATH.with_name('run-mtp-metadata-client-campaign.py'))
        prefix='raw/client';data={};strict={};contexts={};arms=[];sequence=[];counts={'control':0,'candidate':0}
        def rows(mode,native=False):
            return [{'rank':rank,'source_sha256':client.SOURCE_SHA,'mode':mode,
                     'installed':mode!='unwrapped-control','wrapper_active':mode!='unwrapped-control',
                     'candidate_ast_sha256':client.CANDIDATE_AST if mode!='unwrapped-control' else None,
                     'native_gate_passed':native,'calls':dict(counts) if mode!='unwrapped-control' else {}} for rank in (0,1)]
        def rpc(method,mode,native=False,response=None):
            result=response or {'results':rows(mode,native)};sequence.append(result)
            stem=f'{prefix}/rpc-{len(sequence):02d}-{method}'
            data[stem+'-request.json']=collector.encoded({'method':method,'args':[],'kwargs':{'mode':mode} if method=='mtp_transfer_set_mode' else {}})
            data[stem+'-response.json']=collector.encoded(result)
            return result['results']
        rpc('mtp_transfer_status','unwrapped-control');rpc('mtp_transfer_status','unwrapped-control');rpc('mtp_transfer_prepare','control')
        cases=[{'case':f'case-{i//2}','full_graph_metadata':bool(i%2),'exact_fields':24,'aliases_equal':True,
                'retained_views_equal':True,'inputs_unmodified_except_documented_cache':True,'buffer_reuses':3} for i in range(36)]
        native={'results':[{'rank':rank,'result':{'passed':True,'case_count':36,'cases':cases},'status':rows('control',True)[rank]} for rank in (0,1)]}
        rpc('mtp_transfer_native_gate','control',True,native)
        for label,mode in client.ARMS:
            before=rpc('mtp_transfer_set_mode',mode,True);counts[mode]+=10;after=rpc('mtp_transfer_status',mode,True)
            sp=f'{prefix}/{label}/strict';cp=f'{prefix}/{label}/context'
            data[sp+'/performance.json']=collector.encoded({'fixture':label});data[cp+'/summary.json']=collector.encoded({'fixture':label})
            strict[sp]={'class_balanced_decode_tok_s':50.0};contexts[cp]={'by_length':{'512':{'prefill':2000}}}
            arms.append({'label':label,'mode':mode,'rank_status_before':before,'rank_status_after':after,'matched_metadata_calls_per_rank':10,
                         'strict_performance_sha256':collector.sha(data[sp+'/performance.json']),'context_summary_sha256':collector.sha(data[cp+'/summary.json']),
                         'class_balanced_decode_tok_s':50.0,'context_by_length':contexts[cp]['by_length'],'complete_outputs_match_frozen':True})
        final=rpc('mtp_transfer_set_mode','control',True)
        data['source.py']=b'valid source'
        prereg={'files':[{'path':'/source.py','sha256':collector.sha(data['source.py'])}]}
        data[prefix+'/preregistration.json']=collector.encoded(prereg)
        campaign={'refreshed_unwrapped_base_12_of_12_exact':True,'native_36_cases_both_ranks_passed':True,'arms':arms,
                  'final_rank_status':final,'preregistration_sha256':collector.sha(data[prefix+'/preregistration.json'])}
        selection={'client_dir':'client','source_paths':{'source.py':{'path':'/source.py'}}}
        result=collector.completed_client_replay(data,selection,campaign,client,strict,contexts)
        self.assertEqual(result['ordered_rpc_transitions_verified'],13)
        bad=copy.deepcopy(campaign);bad['arms'][0]['matched_metadata_calls_per_rank']=9
        with self.assertRaises(ValueError):collector.completed_client_replay(data,selection,bad,client,strict,contexts)
        data['source.py']=b'drifted source'
        with self.assertRaises(ValueError):collector.completed_client_replay(data,selection,campaign,client,strict,contexts)

    def test_selection_preserves_controller_snapshot_and_failed_stages(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);packet=root/'packet';packet.mkdir();frozen=root/'frozen';frozen.mkdir()
            (frozen/'control-identity.json').write_text('{}')
            for directory in ('control-strict','control-context'):
                (frozen/directory).mkdir();(frozen/directory/'fixture.json').write_text('{}')
            for stage in ('communication-native-01','communication-native-02'):
                (root/stage).mkdir();(root/stage/'state.json').write_text(json.dumps({'finished':'test','stop_confirmed':True,'status':'failed'}))
                (root/stage/'ABORTED').write_text('retained setup failure')
            closure={'status':'closed-after-gpu-fault','finished_at':'test','final_service':{'status':'ready'},'client_not_run_reason':'explicit fixture'}
            (root/'campaign-completion.json').write_text(json.dumps(closure))
            (root/'FAULT.json').write_text('{"fault":"preserved"}')
            (root/'communication-native-02/GPU-FAULT.json').write_text('{"fault":"preserved"}')
            (root/'communication-native-02/postflight.json').write_text('{}')
            server=root/'research-server';server.mkdir();snapshot=server/'research-extension';snapshot.mkdir()
            (snapshot/'mtp_transfer_worker.py').write_text('# frozen fixture')
            (server/'state.json').write_text('{"status":"ready"}')
            (server/'server.log').write_text('point-in-time log')
            (server/'STOP_UNCONFIRMED').write_text('preserved uncertainty')
            (server/'container-inspect.json').write_text('{}')
            args=types.SimpleNamespace(root=root,packet=packet,final_receipt='campaign-completion.json',
                operator_stage=['communication-native-01','communication-native-02'],client_dir='client',server_dir='research-server',
                frozen_root=frozen,running_log_snapshot_label=None)
            with self.assertRaises(ValueError):collector.select(args)
            args.running_log_snapshot_label='test-snapshot'
            data,_=collector.select(args)
            for name in ('sources/run-mtp-lossless-server.py',
                         'repository/packages/qwen38-27b-fp8-tp2-b70/scripts/serve.py',
                         'raw/research-server/research-extension/mtp_transfer_worker.py',
                         'raw/research-server/STOP_UNCONFIRMED','raw/research-server/container-inspect.json',
                         'raw/communication-native-01/ABORTED','raw/communication-native-02/ABORTED',
                         'raw/FAULT.json','raw/communication-native-02/GPU-FAULT.json','raw/communication-native-02/postflight.json',
                         'running-log-snapshot/test-snapshot/server.log','frozen/control-identity.json'):
                self.assertIn(name,data)
            (root/'campaign-completion.json').write_text('{}')
            with self.assertRaises(ValueError):collector.select(args)

if __name__=='__main__':unittest.main()
