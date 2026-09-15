#!/usr/bin/env python3
"""Stdlib-only packet12 lifecycle and inherited exact-output gate regression."""
import ast
import copy
import hashlib
import importlib.util
import json
import io
import struct
from types import SimpleNamespace
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
LANE = Path(__file__).resolve().parents[1]

def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, LANE / 'scripts' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

old = load('host_old_test_fixtures', 'test-host-embedding-screen-stdlib.py')
client = load('host_screen_v3_test', 'run-host-embedding-screen-v3.py')
v = client.validators
old.v, old.client = v, client
S, M, CONTRACT = old.S, old.M, old.CONTRACT
SHARED = dict(zip(sorted(v.SHARED_KEYS), range(500, 507)))


def memory(stage, allocation):
    values = {'MemTotal': 256 * 1024**3, 'MemAvailable': 128 * 1024**3,
              'MemFree': 64 * 1024**3, 'SwapFree': 0, 'SwapTotal': 32 * 1024**3}
    raw = ''.join(f'{key}: {value // 1024} kB\n' for key, value in values.items())
    return {'schema': 'ltx.host-embedding-memory-admission.v1', 'stage': stage,
        'tracked_allocation_bytes': allocation, 'existing_headroom_bytes': v.HEADROOM_BYTES,
        'required_available_bytes': allocation + v.HEADROOM_BYTES,
        'observed': {'source': '/proc/meminfo', 'raw': raw, 'bytes': values},
        'passed': True, 'swap_counted_as_headroom': False, 'runtime_memory_settings_changed': False}


def components(generation):
    mode = 'host-table' if generation == 2 else 'control'
    started = {'schema': 'ltx.host-embedding-components.v2', 'server_identity_sha256': S,
        'model_verification_sha256': M, 'generation': generation, 'previous_generation': generation - 1,
        'placement': 'split', 'encoder_mode': mode, 'previous_mode': None if generation == 1 else
        ('control' if mode == 'host-table' else 'host-table'),
        'generated_output_cache': False, 'prompt_encoding_cache': False, 'status': 'started',
        'retained': 'nonencoder components across all generations; one current CLIP'}
    result = dict(started, status='completed', text_encoder_load_device='xpu:2', vae_devices=['xpu:3','xpu:3'],
        model_load_device='xpu:0', encoder_initial_ownership=old.report(mode, True), shared_owner_ids=dict(SHARED),
        memory_geometry={'checkpoint_tensor_bytes': v.CHECKPOINT_TENSOR_BYTES, 'checkpoint_header_bytes': 83880,
            'registered_state_bytes': v.REGISTERED_STATE_BYTES,
            'construction_overlap_bytes': v.CHECKPOINT_TENSOR_BYTES + v.REGISTERED_STATE_BYTES,
            'existing_headroom_bytes': v.HEADROOM_BYTES},
        construction_memory=memory('before-construction', v.CHECKPOINT_TENSOR_BYTES + v.REGISTERED_STATE_BYTES),
        constructed_memory=memory('after-construction', 0))
    if generation > 1:
        result.update(shared_owner_ids_before=dict(SHARED), released_memory=memory('after-release', 0))
        previous, retirement = old.retired(started['previous_mode'])
        allocation = sum(r['bytes'] for group in ('parameters', 'buffers')
                         for r in retirement['before']['encoder'][group]['records'] if r['device'] != 'cpu')
        result['restore_memory'] = memory('before-restore', allocation)
    return started, result


def validate_component(started, result):
    g = result['generation']
    return v.component(started, result, contract=CONTRACT, mode=result['encoder_mode'], generation=g,
        server_sha=S, model_sha=M, previous_component=components(g - 1)[1] if g > 1 else None)


class Tests(old.Tests):
    def test_component_sequence_and_initial_cpu(self):
        for g in (1, 2, 3):
            started, result = components(g)
            validate_component(started, result)
            result['encoder_initial_ownership']['encoder']['accounting']['reported_loaded_weight_bytes'] = 10
            with self.assertRaises(RuntimeError): validate_component(started, result)

    def test_component_v2_shared_owners_and_geometry_refusals(self):
        mutations = [(('schema',), 'ltx.host-embedding-components.v1'),
            (('shared_owner_ids', 'model'), 9999), (('shared_owner_ids_before', 'upscaler'), 7777),
            (('memory_geometry', 'construction_overlap_bytes'), 1),
            (('construction_memory', 'required_available_bytes'), 1),
            (('constructed_memory', 'passed'), False), (('released_memory', 'stage'), 'before-restore')]
        for path, value in mutations:
            started, result = components(2)
            target = result
            for key in path[:-1]: target = target[key]
            target[path[-1]] = value
            with self.subTest(path=path), self.assertRaises(RuntimeError): validate_component(started, result)

    def test_retired_weakrefs_and_native_registry_refusals(self):
        for previous_mode in v.MODES:
            keys = ['clip', 'group', 'encoder_patcher', 'encoder_model']
            if previous_mode == 'host-table': keys += ['host_owner', 'host_patcher', 'host_model', 'host_weight']
            old_g = 1 if previous_mode == 'control' else 2
            report = {'server_identity_sha256': S, 'model_verification_sha256': M,
                'old_generation': old_g, 'new_generation': old_g + 1, 'shared_owner_ids': SHARED,
                'all_retired_weakrefs_dead': True, 'retired_patcher_ids_absent_from_registry': True,
                'checked': sorted(keys), 'native_registry_cleanup':
                'cleanup_models after weak-finalizer cleanup; no direct list mutation'}
            kw = dict(previous_mode=previous_mode, old_generation=old_g, new_generation=old_g+1,
                      shared=SHARED, server_sha=S, model_sha=M)
            v.released(report, **kw)
            for key, value in [('all_retired_weakrefs_dead', False), ('retired_patcher_ids_absent_from_registry', False),
                               ('checked', ['clip']), ('shared_owner_ids', dict(SHARED, model=9999))]:
                mutated = dict(report, **{key: value})
                with self.subTest(mode=previous_mode, key=key), self.assertRaises(RuntimeError):v.released(mutated, **kw)

    def test_memory_raw_floor_no_swap_and_all_standalone_stages(self):
        for generation in (1, 2, 3):
            _, result = components(generation)
            retirement = old.retired('control' if generation == 2 else 'host-table')[1] if generation > 1 else None
            fields = ['construction_memory', 'constructed_memory'] + (['restore_memory','released_memory'] if generation > 1 else [])
            reports = {result[k]['stage']: result[k] for k in fields}
            v.transition_memory(result, retirement, reports)
            for key, value in [('passed', False), ('swap_counted_as_headroom', True),
                               ('runtime_memory_settings_changed', True), ('tracked_allocation_bytes', 0)]:
                bad = copy.deepcopy(result['construction_memory']); bad[key] = value
                with self.subTest(key=key), self.assertRaises(RuntimeError):
                    v.memory(bad, 'before-construction', v.CHECKPOINT_TENSOR_BYTES + v.REGISTERED_STATE_BYTES)
            bad = copy.deepcopy(reports); bad.pop('after-construction')
            with self.assertRaises(RuntimeError):v.transition_memory(result, retirement, bad)
            bad = copy.deepcopy(reports);bad['after-construction']['observed']['bytes']['MemAvailable'] += 1024
            with self.assertRaises(RuntimeError):v.transition_memory(result, retirement, bad)
        floor = v.CHECKPOINT_TENSOR_BYTES + v.REGISTERED_STATE_BYTES
        bad = memory('before-construction', floor)
        bad['observed']['raw'] = bad['observed']['raw'].replace('MemAvailable: 134217728', 'MemAvailable: 1')
        bad['observed']['bytes']['MemAvailable'] = 1024
        with self.assertRaises(RuntimeError):v.memory(bad, 'before-construction', floor)

    def test_frozen_numerical_and_error_handling_functions_unchanged(self):
        def functions(path):
            return {n.name: ast.dump(n, include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
        previous = functions(LANE/'scripts/run-host-embedding-screen-v2.py')
        current = functions(LANE/'scripts/run-host-embedding-screen-v3.py')
        for name in ('schedule', 'expected_graph', 'normalized', 'validate_node_info', 'paired_results', 'run_with_post_snapshot'):
            self.assertEqual(previous[name], current[name], name)
        old_v = functions(LANE/'scripts/ltx_host_embedding_receipts.py')
        new_v = functions(LANE/'scripts/ltx_host_embedding_receipts_v3.py')
        for name in ('inventory','ownership','placement','unload','same_owners','expected_inventory'):
            self.assertEqual(old_v[name], new_v[name], name)
        tree = ast.parse((LANE/'scripts/run-host-embedding-screen-v3.py').read_text())
        campaign = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run_campaign')
        text=ast.unparse(campaign)
        self.assertIn("{'images', 'video_latent', 'audio_latent', 'waveform'}",text)
        self.assertIn("x['bitwise_equal'] is True",text)
        self.assertIn('eligible[:-3]',text)
        self.assertLess(text.index('cold_admission(identity_sha, args, common)'),text.index('run_with_post_snapshot('))
        self.assertNotIn('torch',sys.modules)

    def test_cold_budget_boundary_identity_and_no_swap_credit(self):
        contract = json.loads((LANE/'data/host-embedding-cold-memory-contract-01.json').read_text())
        self.assertEqual(hashlib.sha256((LANE/'data/host-embedding-cold-memory-contract-01.json').read_bytes()).hexdigest(), client.COLD_CONTRACT_SHA)
        required = contract['required_available_bytes']
        for available_kib, accepted in (((required + 1023)//1024, True), (required//1024, False)):
            observed = memory('unused',0)['observed']
            observed['bytes']['MemAvailable'] = available_kib*1024
            observed['raw'] = ''.join(f'{key}: {value//1024} kB\n' for key,value in observed['bytes'].items())
            report = {'schema':'ltx.host-embedding-cold-memory-admission.v1', 'stage':'before-initial-component-allocation',
                'server_identity_sha256':S,'source_contract_sha256':client.COLD_CONTRACT_SHA,
                'required_available_bytes':required,'observed':observed,'passed':accepted,
                'server_args_sha256':'a'*64, 'source_identity':{'source_contract_sha256':client.COLD_CONTRACT_SHA,
                    'source_and_saved_evidence_hashes_match':True,'full_weight_payload_rehashed':False,
                    'headers':{n:{k:h[k] for k in ('path','header_sha256','header_bytes','file_bytes')} for n,h in contract['headers'].items()}},
                'swap_counted_as_headroom':False,'runtime_memory_settings_changed':False}
            v.cold_memory(report,contract,client.COLD_CONTRACT_SHA,S,require_pass=False)
            if accepted:
                v.cold_memory(report,contract,client.COLD_CONTRACT_SHA,S)
            else:
                with self.assertRaises(RuntimeError):v.cold_memory(report,contract,client.COLD_CONTRACT_SHA,S)
            for field,value in [('source_contract_sha256','wrong'),('server_identity_sha256','wrong'),
                                ('swap_counted_as_headroom',True),('required_available_bytes',1),('passed',not accepted)]:
                bad = dict(report,**{field:value})
                with self.subTest(field=field),self.assertRaises(RuntimeError):
                    v.cold_memory(bad,contract,client.COLD_CONTRACT_SHA,S,require_pass=False)

    def test_request_error_remains_primary_with_missing_server_snapshot(self):
        primary = RuntimeError('original profile disconnect')
        def request():raise primary
        def snapshot():raise FileNotFoundError('server disappeared')
        report={}
        with self.assertRaises(RuntimeError) as caught:
            client.run_with_post_snapshot(request,snapshot,report)
        self.assertIs(caught.exception,primary)
        self.assertIn('after_snapshot_error',report)
        with self.assertRaises(FileNotFoundError):
            client.run_with_post_snapshot(lambda:None,snapshot,{})

    def test_bounded_header_identity_rejects_length_hash_extent_and_mutation(self):
        raw = b'{"fixture":true}'
        expected = {'header_bytes':len(raw),'header_sha256':hashlib.sha256(raw).hexdigest(),
                    'tensor_payload_bytes':100,'file_bytes':8+len(raw)+100}
        class Model:
            def __init__(self, data=None, size=None, changed=False):
                self.data = struct.pack('<Q',len(raw))+raw if data is None else data
                self.size = expected['file_bytes'] if size is None else size
                self.calls=0;self.changed=changed
            def is_file(self):return True
            def is_symlink(self):return False
            def open(self,mode):return io.BytesIO(self.data)
            def stat(self):
                self.calls += 1
                return SimpleNamespace(st_dev=1,st_ino=2,st_size=self.size,st_mtime_ns=self.calls if self.changed else 3,st_ctime_ns=4)
            def __str__(self):return 'synthetic-header-only'
        self.assertEqual(client.cold_header(Model(),expected)['header_bytes'],len(raw))
        for model in (Model(data=b'bad'),Model(data=struct.pack('<Q',len(raw)+1)+raw),
                      Model(data=struct.pack('<Q',len(raw))+b'x'*len(raw)),Model(size=1),Model(changed=True)):
            with self.assertRaises(RuntimeError):client.cold_header(model,expected)

    def test_cold_header_and_config_checks_precede_fresh_meminfo(self):
        tree=ast.parse((LANE/'scripts/run-host-embedding-screen-v3.py').read_text())
        fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='cold_admission')
        text=ast.unparse(fn)
        self.assertLess(text.index('cold_source_identity()'),text.index("Path('/proc/meminfo').read_text()"))
        self.assertLess(text.index('cold_server_args(args, common)'),text.index("Path('/proc/meminfo').read_text()"))
        # Actual frozen launcher argument expression, with caller variable names normalized.
        launch=ast.parse((LANE/'scripts/serve-encoder.py').read_text())
        launcher=next(n for n in launch.body if isinstance(n,ast.FunctionDef) and n.name=='server_args')
        expected=next(n.value for n in launcher.body if isinstance(n,ast.Return))
        checked=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='cold_server_args')
        observed=next(n.value for n in checked.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='expected' for t in n.targets))
        self.assertEqual(ast.dump(expected),ast.dump(observed))

if __name__ == '__main__':
    unittest.main(verbosity=2)
