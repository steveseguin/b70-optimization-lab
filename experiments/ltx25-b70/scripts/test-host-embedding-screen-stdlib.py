#!/usr/bin/env python3
"""Offline metadata/graph mutation tests. No native imports or endpoint calls."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('host_screen_test', LANE / 'scripts/run-host-embedding-screen.py')
client = importlib.util.module_from_spec(spec)
spec.loader.exec_module(client)
v = client.validators
CONTRACT = json.loads((LANE / 'data/host-embedding-registered-contract-01.json').read_text())
S, M = 's' * 64, 'm' * 64


def inspection(mode, initial=False, host=False):
    expected = v.expected_inventory(CONTRACT, mode)
    if host:
        table = next(r for r in CONTRACT['parameters'] if r['name'] == v.TABLE_NAME)
        expected = {'parameters': [dict(table, name='embedding.weight')], 'buffers': []}
    result = {}
    for group in ('parameters', 'buffers'):
        rows = []
        by = {}
        for n, row in enumerate(expected[group], 1):
            device = 'cpu' if initial or host else 'xpu:2'
            owner = 100000 + n + (10000 if group == 'buffers' else 0)
            if row['name'] in (v.TABLE_NAME, 'embedding.weight'):
                owner = 999999
            rows.append(dict(row, owner_id=owner, device=device))
            entry = by.setdefault(device + '/' + row['dtype'], {'tensors': 0, 'bytes': 0})
            entry['tensors'] += 1; entry['bytes'] += row['bytes']
        result[group] = {'records': rows, 'count': len(rows), 'bytes': sum(r['bytes'] for r in rows), 'by_device_dtype': by}
    load_device = 'cpu' if host else 'xpu:2'
    size = sum(r['bytes'] for r in expected['parameters']) + sum(r['bytes'] for r in expected['buffers'] if r['persistent'])
    result['accounting'] = {'offload_device': 'cpu', 'load_device': load_device,
        'crop_option': False, 'patcher_small_state_option': False, 'model_small_state_policy': False, 'is_dynamic': False,
        'reported_model_size_bytes': size, 'reported_loaded_weight_bytes': 0 if initial else size,
        'reported_offload_buffer_bytes': 0, 'small_buffers_loaded': False, 'marked_modules': [],
        'registered_parameter_bytes_on_load_device': sum(r['bytes'] for r in result['parameters']['records'] if r['device'] == load_device),
        'registered_persistent_buffer_bytes_on_load_device': sum(r['bytes'] for r in result['buffers']['records'] if r['persistent'] and r['device'] == load_device)}
    return result


def report(mode='host-table', initial=False, ordinal=1):
    encoder = inspection(mode, initial)
    r = {'schema': 'ltx.host-embedding-placement.v1', 'mode': mode, 'encodes_completed': 0 if initial else ordinal,
        'original_combined_bytes': CONTRACT['original_combined_bytes'], 'encoder': encoder, 'host': None, 'owner': None,
        'quality_qualified': False, 'speed_qualified': False, 'embedding_observation_limit': 4,
        'embedding_observations': [] if initial else [{'ordinal': 1,
            'input_ids': {'shape': [1,1024], 'dtype': 'torch.int64', 'device': 'xpu:2'},
            'scaled_embedding': {'shape': [1,1024,3840], 'dtype': 'torch.float32', 'device': 'xpu:2'}}],
        'last_load': None if initial else {'memory_required': 5000, 'patcher_ids': [123,456] if mode == 'host-table' else [123],
                                          'force_full_load': False, 'reserve_override': False}}
    if mode == 'host-table':
        r['host'] = inspection(mode, initial, host=True)
        r['owner'] = {'schema': 'ltx.host-embedding-ownership.v1', 'host_owner_id': 789, 'host_weight_id': 888,
            'host_device': 'cpu', 'host_dtype': 'torch.bfloat16', 'host_registered_bytes': v.TABLE_BYTES,
            'original_combined_bytes': CONTRACT['original_combined_bytes'], 'execution_device': 'xpu:2',
            'encoder_eligible_bytes': CONTRACT['original_combined_bytes'] - v.TABLE_BYTES,
            'encoder_reported_loaded_bytes': encoder['accounting']['reported_loaded_weight_bytes'],
            'inference_tensor': True, 'weight_version_tracked': False, 'native_qualified': False}
    if not initial:
        r.update(server_identity_sha256=S, model_verification_sha256=M, stage='post_encode', run_name='test-r01-host-table-boat',
                 passed=True, generated_output_cache=False, prompt_encoding_cache=False)
    return r


def validate(r, initial=None, previous=None):
    v.placement(r, contract=CONTRACT, run='test-r01-host-table-boat', mode=r['mode'], ordinal=r['encodes_completed'],
                server_sha=S, model_sha=M, initial=initial or report(r['mode'], True), previous=previous)


def retired(mode):
    previous = report(mode)
    before = copy.deepcopy(previous)
    before['embedding_observations'] = []
    after = inspection('control', True)
    # Match all original owner IDs after restoring the extracted registration.
    owners = {r['name']: r['owner_id'] for r in before['encoder']['parameters']['records']}
    if mode == 'host-table':
        owners[v.TABLE_NAME] = before['host']['parameters']['records'][0]['owner_id']
    for row in after['parameters']['records']:
        row['owner_id'] = owners[row['name']]
    receipt = {'schema': 'ltx.host-embedding-unload.v1', 'server_identity_sha256': S, 'model_verification_sha256': M,
        'old_generation': 1 if mode == 'control' else 2, 'new_generation': 2 if mode == 'control' else 3,
        'old_mode': mode, 'new_mode': 'host-table' if mode == 'control' else 'control',
        'before': before, 'after_encoder': after, 'after_host_registered_bytes': 0,
        'original_ownership_restored': True, 'all_shared_clones_retired': True}
    return previous, receipt


def validate_retired(previous, receipt):
    return v.unload(receipt, contract=CONTRACT, previous=previous,
        old_generation=receipt['old_generation'], new_generation=receipt['new_generation'], mode=receipt['new_mode'],
        server_sha=S, model_sha=M)


class Tests(unittest.TestCase):
    def test_actual_saved_control_metadata_contract(self):
        p = Path(CONTRACT['source_path'])
        self.assertEqual(hashlib.sha256(p.read_bytes()).hexdigest(), CONTRACT['source_sha256'])
        actual = json.loads(p.read_text())['inspection']
        v.inventory(actual, v.expected_inventory(CONTRACT, 'control'))
        self.assertEqual((len(CONTRACT['parameters']), len(CONTRACT['buffers'])), (634, 51))
        self.assertEqual(CONTRACT['original_combined_bytes'], 26231582820)

    def test_initial_control_host_and_new_encode(self):
        for mode in v.MODES:
            initial = report(mode, True)
            v.ownership(initial, CONTRACT, mode, initial=True)
            r = report(mode)
            validate(r, initial)
            next_r = report(mode, ordinal=2)
            validate(next_r, initial, r)

    def test_identity_metadata_and_accounting_rejections(self):
        paths = [(('server_identity_sha256',), 'changed'), (('encodes_completed',), True),
            (('prompt_encoding_cache',), True), (('last_load','reserve_override'), True),
            (('last_load','force_full_load'), True), (('last_load','patcher_ids'), [123]),
            (('last_load','memory_required'), float('nan')), (('host','accounting','reported_loaded_weight_bytes'), 0),
            (('owner','host_device'), 'xpu:2'), (('encoder','accounting','reported_loaded_weight_bytes'), 1),
            (('encoder','accounting','is_dynamic'), True), (('embedding_observation_limit',), 5)]
        for path, value in paths:
            with self.subTest(path=path):
                r = report(); target = r
                for k in path[:-1]: target = target[k]
                target[path[-1]] = value
                with self.assertRaises(RuntimeError): validate(r)

    def test_geometry_and_individual_state_rejections(self):
        for field, value in [('shape',[1,512]), ('device','cpu'), ('dtype','torch.int32')]:
            r=report(); r['embedding_observations'][0]['input_ids'][field]=value
            with self.assertRaises(RuntimeError): validate(r)
        for field, value in [('shape',[1,1024,3072]), ('device','cpu'), ('dtype','torch.bfloat16')]:
            r=report(); r['embedding_observations'][0]['scaled_embedding'][field]=value
            with self.assertRaises(RuntimeError): validate(r)
        for group in ('parameters','buffers'):
            r=report(); r['encoder'][group]['records'][0]['device']='cpu'
            with self.assertRaises(RuntimeError): validate(r)
        r=report(); r['embedding_observations'] *= 2
        with self.assertRaises(RuntimeError): validate(r)
        r=report(); r['host']['parameters']['records'][0]['shape']=[262143,3840]
        with self.assertRaises(RuntimeError): validate(r)

    def test_owner_continuity_and_repeated_encode_rejections(self):
        first=report(); second=report(ordinal=2)
        second['owner']['host_weight_id'] += 1
        with self.assertRaises(RuntimeError): validate(second, previous=first)
        second=report(ordinal=2); second['encoder']['parameters']['records'][2]['owner_id'] += 1
        with self.assertRaises(RuntimeError): validate(second, previous=first)
        second=report(ordinal=2); second['last_load']['patcher_ids']=[345,456]
        with self.assertRaises(RuntimeError): validate(second, previous=first)
        with self.assertRaises(RuntimeError):
            v.placement(first, contract=CONTRACT, run=first['run_name'], mode='host-table', ordinal=2,
                server_sha=S, model_sha=M, initial=report('host-table',True), previous=first)

    def test_both_retirements_and_incomplete_restoration_reject(self):
        for mode in v.MODES:
            previous, receipt = retired(mode)
            validate_retired(previous, receipt)
            for key, value in [('after_host_registered_bytes',v.TABLE_BYTES), ('all_shared_clones_retired',False)]:
                r=copy.deepcopy(receipt); r[key]=value
                with self.assertRaises(RuntimeError): validate_retired(previous,r)
            r=copy.deepcopy(receipt); r['after_encoder']['parameters']['records'][0]['owner_id']+=1
            with self.assertRaises(RuntimeError): validate_retired(previous,r)
            r=copy.deepcopy(receipt); r['after_encoder']['accounting']['reported_loaded_weight_bytes']=1
            with self.assertRaises(RuntimeError): validate_retired(previous,r)

    def test_component_sequence_and_initial_cpu(self):
        for generation, mode in [(1,'control'),(2,'host-table'),(3,'control')]:
            started={'schema':'ltx.host-embedding-components.v1','server_identity_sha256':S,'model_verification_sha256':M,
                'generation':generation,'previous_generation':generation-1,'placement':'split','encoder_mode':mode,
                'previous_mode':None if generation==1 else ('control' if mode=='host-table' else 'host-table'),
                'generated_output_cache':False,'prompt_encoding_cache':False,'status':'started'}
            result=dict(started,status='completed',text_encoder_load_device='xpu:2',vae_devices=['xpu:3','xpu:3'],
                model_load_device='xpu:0',encoder_initial_ownership=report(mode,True))
            kw=dict(contract=CONTRACT,mode=mode,generation=generation,server_sha=S,model_sha=M)
            v.component(started,result,**kw)
            result['encoder_initial_ownership']['encoder']['accounting']['reported_loaded_weight_bytes']=10
            with self.assertRaises(RuntimeError):v.component(started,result,**kw)

    def test_schedule_pair_sign_and_finite_timing(self):
        rows=client.schedule('test')
        self.assertEqual(len(rows),15)
        self.assertEqual(len({r['run'] for r in rows}),15)
        self.assertEqual([r['generation'] for r in rows if r['initialization']],[1,2,3])
        for r in rows:
            r.update(status='passed',preview_ready_seconds=5 if r['mode']=='host-table' else 6,
                     encoder_node_seconds=1 if r['mode']=='host-table' else 2)
        pairs=client.paired_results(rows)
        self.assertEqual(pairs['paired_samples'],4)
        self.assertTrue(all(p['metrics']['preview_ready_seconds']['host_minus_control_mean']==-1 for p in pairs['pairs']))
        rows[1]['encoder_node_seconds']=float('inf')
        with self.assertRaises(RuntimeError): client.paired_results(rows)
        with self.assertRaises(RuntimeError): client.schedule('../unsafe')

    def test_graph_packet_scope_and_no_native_imports(self):
        base=json.loads((LANE/'data/speed-resident-split-api.json').read_text())
        packet=client.ROOT/'prepared-encoder-host-embedding-11'
        for mode in v.MODES:
            graph=client.expected_graph(base,mode)
            expected=json.loads((packet/'graphs'/f'host-embedding-{mode}.json').read_text())
            self.assertEqual(client.normalized(graph),client.normalized(expected))
            self.assertEqual(graph['374']['class_type'],'VAEDecode')
            self.assertNotIn('422',graph)
        self.assertNotIn('torch',sys.modules)
        self.assertFalse(any(k.startswith('comfy.') for k in sys.modules))

    def test_exact_node_registration_contract(self):
        for name in ['LTXHostEmbeddingComponents','LTXHostEmbeddingPlacementCheck']:
            if name.endswith('Components'):
                inputs={'placement':[['split']],'encoder_mode':[['control','host-table']]}
                outputs=['MODEL','CLIP','VAE','VAE','LATENT_UPSCALE_MODEL']; names=['model','clip','video_vae','audio_vae','upscaler']
            else:
                inputs={'clip':['CLIP'],'conditioning':['CONDITIONING'], 'run_name':['STRING',{'default':'assign-unique-request-name'}],
                        'encoder_mode':[['control','host-table']]}; outputs=names=['CONDITIONING']
            obj={name:{'input':{'required':inputs},'output':outputs,'output_name':names,'output_is_list':[False]*len(outputs),
                'is_input_list':False,'output_node':False,'name':name,'category':'lab/validation',
                'python_module':'custom_nodes.ltx_host_embedding_lab'}}
            client.validate_node_info(obj,name)
            obj[name]['python_module']='custom_nodes.old'
            with self.assertRaises(RuntimeError):client.validate_node_info(obj,name)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    print(json.dumps({'status':'passed' if result.wasSuccessful() else 'failed','tests_run':result.testsRun,
        'native_imports':False,'endpoint_calls':0,'source_sha256s':{str(p.relative_to(LANE)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [Path(__file__),LANE/'scripts/run-host-embedding-screen.py',LANE/'scripts/ltx_host_embedding_receipts.py',
                  LANE/'data/host-embedding-registered-contract-01.json']}}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
