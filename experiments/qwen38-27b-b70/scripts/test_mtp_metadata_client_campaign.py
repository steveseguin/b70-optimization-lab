"""CPU fail-closed client admission tests. No endpoint or GPU access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

PATH=Path(__file__).with_name('run-mtp-metadata-client-campaign.py')
spec=importlib.util.spec_from_file_location('mtp_client',PATH)
client=importlib.util.module_from_spec(spec);spec.loader.exec_module(client)


def valid_status():
    return {'results':[{'rank':rank,'source_sha256':client.SOURCE_SHA,'mode':'control','installed':True,'wrapper_active':True,'candidate_ast_sha256':client.CANDIDATE_AST,'native_gate_passed':True,'calls':{'control':0,'candidate':0}} for rank in (0,1)]}


class ClientGuards(unittest.TestCase):
    def test_idle_requires_both_metrics(self):
        with self.assertRaises(RuntimeError):client.idle_metrics('vllm:num_requests_running 0\n')
    def test_idle_refuses_queued_or_running(self):
        for running,waiting in [(1,0),(0,1),(float('nan'),0),(float('inf'),0)]:
            with self.assertRaises(RuntimeError):client.idle_metrics(f'vllm:num_requests_running {running}\nvllm:num_requests_waiting {waiting}\n')
    def test_idle_checks_all_series(self):
        text='vllm:num_requests_running{model_name="a"} 0\nvllm:num_requests_waiting{model_name="a"} 0\n'
        self.assertEqual(client.idle_metrics(text),{'running':[0.0],'waiting':[0.0]})
        with self.assertRaises(RuntimeError):client.idle_metrics(text+'vllm:num_requests_running{model_name="b"} 1\n')
    def test_two_rank_valid(self):
        self.assertEqual(len(client.statuses(valid_status(),'control',True)),2)
    def test_disagreement_rejected(self):
        for key,value in [('mode','candidate'),('source_sha256','wrong'),('wrapper_active',False),('candidate_ast_sha256','wrong'),('native_gate_passed',False)]:
            data=valid_status();data['results'][1][key]=value
            with self.assertRaises(RuntimeError):client.statuses(data,'control',True)
    def test_rank_duplicates_and_boolean_rejected(self):
        for value in (0,True):
            data=valid_status();data['results'][1]['rank']=value
            with self.assertRaises(RuntimeError):client.statuses(data,'control',True)
    def test_unwrapped_requires_no_installed_wrapper(self):
        data=valid_status()
        for row in data['results']:row['mode']='unwrapped-control'
        with self.assertRaises(RuntimeError):client.statuses(data,'unwrapped-control')
    def test_parity_zero_exit_report_is_not_success(self):
        data={'comparison':{'exact_prompts':11,'total_prompts':12,'complete_token_arrays_exact':False},'qualification':{'strict_pair_qualified':False}}
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'parity.json';path.write_text(json.dumps(data))
            with self.assertRaises(RuntimeError):client.parity_gate(path)
            data['comparison'].update(exact_prompts=12,complete_token_arrays_exact=True)
            path.write_text(json.dumps(data))
            with self.assertRaises(RuntimeError):client.parity_gate(path)
            data['qualification']['strict_pair_qualified']=True;path.write_text(json.dumps(data))
            self.assertEqual(client.parity_gate(path),data)
    def test_native_both_ranks_full_case_fields_required(self):
        cases=[{'case':f'fixture-{i//2}','full_graph_metadata':bool(i%2),'exact_fields':24,'aliases_equal':True,'retained_views_equal':True,'inputs_unmodified_except_documented_cache':True,'buffer_reuses':3} for i in range(36)]
        data={'results':[{'rank':rank,'result':{'passed':True,'case_count':36,'cases':copy.deepcopy(cases)},'status':valid_status()['results'][rank]} for rank in (0,1)]}
        self.assertEqual(len(client.native_gate(data)),2)
        for field,value in [('exact_fields',23),('aliases_equal',False),('retained_views_equal',False),('buffer_reuses',0)]:
            invalid=copy.deepcopy(data);invalid['results'][1]['result']['cases'][0][field]=value
            with self.assertRaises(RuntimeError):client.native_gate(invalid)
        invalid=copy.deepcopy(data);invalid['results'][1]['result']['cases'][1]=copy.deepcopy(invalid['results'][1]['result']['cases'][0])
        with self.assertRaises(RuntimeError):client.native_gate(invalid)

    def test_counter_deltas_must_match_both_ranks(self):
        before=valid_status()['results'];after=copy.deepcopy(before)
        for row in after:row['calls']['control']=10
        self.assertEqual(client.counter_gate(before,after,'control'),10)
        after[1]['calls']['control']=9
        with self.assertRaises(RuntimeError):client.counter_gate(before,after,'control')
        after[1]['calls']['control']=10;after[0]['calls']['candidate']=1
        with self.assertRaises(RuntimeError):client.counter_gate(before,after,'control')
    def test_counter_boolean_or_missing_rejected(self):
        for calls in ({'control':True,'candidate':0},{'control':0},None):
            data=valid_status();data['results'][0]['calls']=calls
            with self.assertRaises(RuntimeError):client.statuses(data,'control',True)
    def test_pinned_file_change_stops_admission(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'oracle';p.write_text('original')
            rows=[{'path':str(p),'sha256':client.sha(p)}]
            client.source_gate(rows);p.write_text('modified')
            with self.assertRaises(RuntimeError):client.source_gate(rows)
    def test_empty_server_identity_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name,value in [('launch.json',{}),('state.json',{}),('image.json',[])]:
                (root/name).write_text(json.dumps(value))
            with self.assertRaises(RuntimeError):client.server_identity_gate(root/'launch.json','model')
    def test_controller_identity_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);snapshot=root/'research-extension';snapshot.mkdir()
            commands=['--model','/model','--tensor-parallel-size','2','--dtype','float16','--quantization','fp8',
                      '--kv-cache-dtype','auto','--max-model-len','33024','--max-num-seqs','1','--no-enable-prefix-caching',
                      '--speculative-config','{"method":"qwen3_next_mtp","num_speculative_tokens":1}',
                      '--served-model-name','model']
            original={'command':commands,'env':['VLLM_USE_V2_MODEL_RUNNER=0']}
            origin=root/'original.json';origin.write_text(json.dumps(original))
            extensions={}
            for name in ('mtp_transfer_worker.py','mtp_native_metadata_gate.py'):
                target=snapshot/name;target.write_bytes((client.HERE.parent/'probes/mtp-metadata-20260914'/name).read_bytes())
                extensions[name]=client.sha(target)
            launch={'argv':['docker','run','--name','test','-p','127.0.0.1:18129:8000','--restart','no',
                '--cap-add','SYS_PTRACE','--network','bridge','--ipc','host',
                '--mount',f'type=bind,source={client.MODEL_DIR},target=/model,readonly',
                '--mount',f'type=bind,source={snapshot},target=/research,readonly',
                '--env','VLLM_USE_V2_MODEL_RUNNER=0','--env','PYTHONPATH=/research','--env','VLLM_SERVER_DEV_MODE=1',
                client.CONTROL_IMAGE]+commands+['--worker-extension-cls','mtp_transfer_worker.MtpTransferWorkerExtension'],
                'extensions':extensions,'original_control_sha256':client.sha(origin)}
            state={'status':'ready','image_id':client.CONTROL_IMAGE,'port':18129,'container_id':'a'*64,
                   'container_name':'test','boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip()}
            for name,value in [('launch.json',launch),('state.json',state),('image.json',[{'Id':client.CONTROL_IMAGE}])]:
                (root/name).write_text(json.dumps(value))
            with mock.patch.object(client,'ORIGINAL_IDENTITY',origin):
                self.assertEqual(client.server_identity_gate(root/'launch.json','model')[0],launch)
                original_argv=list(launch['argv'])
                cap_index=launch['argv'].index('--cap-add')
                del launch['argv'][cap_index:cap_index+2]
                (root/'launch.json').write_text(json.dumps(launch))
                with self.assertRaises(RuntimeError):client.server_identity_gate(root/'launch.json','model')
                launch['argv']=original_argv;(root/'launch.json').write_text(json.dumps(launch))
                state['status']='starting';(root/'state.json').write_text(json.dumps(state))
                with self.assertRaises(RuntimeError):client.server_identity_gate(root/'launch.json','model')
                state['status']='ready';(root/'state.json').write_text(json.dumps(state))
                (snapshot/'mtp_transfer_worker.py').write_text('changed')
                with self.assertRaises(RuntimeError):client.server_identity_gate(root/'launch.json','model')

if __name__=='__main__':unittest.main()
