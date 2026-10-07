#!/usr/bin/env python3
"""Synthetic CPU fixtures in real capture/request schemas; no model evidence generated."""
import copy
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('reference_gate', HERE / 'reference_gate.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
PLAN = HERE.parent / '20261007-duration110-plan/candidate-plan.json'


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.server = self.root / 'server'; self.server.mkdir()
        self.output = self.root / 'verified.json'; self.contract_path = self.root / 'contract.json'
        self.plan = json.loads(PLAN.read_text())['plan']
        # Only archive dimensions shrink in tests. Pinned real plan/graphs/identities remain unchanged.
        self.shapes = {key: [2] for key in G.SHAPES}
        self.patch = patch.object(G, 'SHAPES', self.shapes); self.patch.start(); self.addCleanup(self.patch.stop)
        model_pin = patch.object(G, 'MODEL_VERIFICATION_SHA256', 'b' * 64)
        model_pin.start(); self.addCleanup(model_pin.stop)
        self.packet = self.root / 'synthetic-packet'
        self.client_source = self.packet / 'resolution/components/request_client.py'
        self.client_source.parent.mkdir(parents=True)
        self.client_source.write_text('# Synthetic policy source; never executed.\n')
        self.write(self.packet / 'manifest.json', {'files': {
            'resolution/components/request_client.py': G.sha(self.client_source.read_bytes())}})
        self.runtime_sha = G.sha((self.packet / 'manifest.json').read_bytes())
        self.identity = {'pid': 12345, 'proc_start_ticks': '5678', 'boot_id': 'synthetic-boot',
                         'source_commit': 'synthetic-only', 'runtime': {'python': 'synthetic'},
                         'rope_compatibility': {'synthetic': True},
                         'source_packet_path': str(self.packet), 'source_packet_manifest_sha256': self.runtime_sha, 'model_verification_sha256': 'b' * 64}
        self.write(self.server / 'server-identity.json', self.identity)
        identity_hash = G.sha((self.server / 'server-identity.json').read_bytes())
        self.contract = {'schema': 'ltx.native-reference-runtime-contract.v1', 'plan_sha256': G.PLAN_SHA,
                         'parent_manifest_sha256': G.PARENT_SHA, 'server_run': str(self.server),
                         'server_identity_sha256': identity_hash, 'successor_manifest_sha256': self.runtime_sha,
                         'model_verification_sha256': 'b' * 64,
                         'request_names': [r['name'] for r in self.plan['requests'][:20]],
                         'runtime_evidence': {str(self.server / 'server-identity.json'): identity_hash}}
        for key, timestamp in [('before_native', 1000), ('after_native', 22000)]:
            state = {'schema': 'ltx.native-reference-state.v1', 'phase': 'native_reference',
                     'server_identity_sha256': identity_hash, 'qualification_id': G.QUALIFICATION_ID,
                     'timestamp_ms': timestamp, 'native_residency_admitted': True,
                     'no_owner_eviction': True, 'oom_to_tiled_refusal_installed': True}
            state.update({k: 0 for k in ['sampler_routes', 'lean_sampler_installs', 'decode_replicas', 'oom_fallback_attempts']})
            state.update({k: [] for k in ['queue_running','queue_pending','pending_encode','pending_sample','pending_decode','pending_save']})
            p = self.root / (key + '.json'); self.write(p, state)
            self.contract[key] = {'path': str(p), 'sha256': G.sha(p.read_bytes())}
        for i, row in enumerate(self.plan['requests'][:20]):
            name = row['name']; req = self.root / 'requests' / name; req.mkdir(parents=True)
            prompt_id = 'synthetic-' + str(i); start = 1100 + i * 1000
            messages = [['execution_start', {'prompt_id': prompt_id, 'timestamp': start}],
                        ['execution_cached', {'prompt_id': prompt_id, 'timestamp': start, 'nodes': []}],
                        ['execution_success', {'prompt_id': prompt_id, 'timestamp': start + 500}]]
            status = {'status_str': 'success', 'completed': True, 'messages': messages}
            self.write(req / 'prompt.json', row['graph'])
            self.write(req / 'submission.json', {'prompt_id': prompt_id, 'number': i, 'node_errors': {}})
            self.write(req / 'history.json', {'prompt': [i, prompt_id, row['graph']], 'status': status})
            self.write(req / 'result.json', {'name': name, 'prompt_id': prompt_id, 'status': status})
            self.write(req / 'identity.json', self.identity)
            nodes = ['364', '344', '348', '368', '374', '358', '414']
            events = [{'type': 'execution_start', 'seconds': 0,
                       'data': {'prompt_id': prompt_id, 'timestamp': start}}]
            events += [{'type': 'executing', 'seconds': n / 20,
                       'data': {'prompt_id': prompt_id, 'node': node}} for n, node in enumerate(nodes)]
            events.append({'type': 'execution_success', 'seconds': .5,
                           'data': {'prompt_id': prompt_id, 'timestamp': start + 500}})
            (req / 'events.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
            text_sha = G.sha(('pipeline-window\n' + row['graph']['364']['inputs']['text']).encode('utf-8'))
            detail = {'text_sha256': text_sha, 'tag': text_sha, 'started_ahead': [], 'pending_after': [],
                      'speculation_miss': False, 'conditioning_fingerprint': G.sha(row['fixture'].encode()),
                      'window_encode': {'window': 64, 'clip_index': row['clip_index']}}
            self.write(self.server / ('pipeline-' + name + '.json'),
                       {'passed': True, 'run_name': name, 'clip_index': row['clip_index'], 'depth': 2,
                        'mode': 'pipeline-window', 'detail': detail, 'server_identity_sha256': identity_hash,
                        'model_verification_sha256': 'b'*64, 'output_size': '640x384', 'speed_only': False, 'frame_count':49})
            out = self.root / 'output/validation' / name; out.mkdir(parents=True)
            header, payload, metadata = {}, b'', {}
            for key in sorted(self.shapes):
                data = struct.pack('<ff', float(i % 10), 1.0)
                header[key] = {'dtype': 'F32', 'shape': [2], 'data_offsets': [len(payload), len(payload) + len(data)]}
                payload += data
                metadata[key] = {'dtype': 'torch.float32', 'shape': [2], 'finite': True, 'sha256': G.sha(data)}
            raw_header = json.dumps(header).encode()
            (out / 'tensors.safetensors').write_bytes(struct.pack('<Q', len(raw_header)) + raw_header + payload)
            self.write(out / 'summary.json', {'run_name': name, 'sample_rate': 48000,
                       'deterministic_enabled': True, 'deterministic_warn_only': False, 'tensors': metadata})
        self.write_contract()

    def write(self, path, value):
        path.write_text(json.dumps(value) + '\n')

    def write_contract(self):
        self.write(self.contract_path, self.contract)
        self.contract_hash = G.sha(self.contract_path.read_bytes())

    def mutate(self, path, fn):
        value = json.loads(path.read_text()); fn(value); self.write(path, value)

    def request(self, index=0):
        return self.root / 'requests' / self.plan['requests'][index]['name']

    def run_gate(self):
        return G.verify_references(self.root, PLAN, self.contract_path, self.contract_hash, self.output)

    def refuse(self):
        with self.assertRaises((ValueError, KeyError, FileNotFoundError)):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def test_complete_synthetic_real_schema_and_reread_receipt(self):
        result = self.run_gate(); self.assertEqual(result['four_tensor_repeat_pairs_exact'], 10)
        verified = G.verify_receipt(self.output, G.sha(self.output.read_bytes()))
        self.assertEqual(len(verified['executions']), 20)
        self.assertNotIn('torch', __import__('sys').modules)

    def test_receipt_exclusive_and_changed_evidence_refused(self):
        self.run_gate()
        with self.assertRaisesRegex(ValueError, 'already exists'): self.run_gate()
        digest = G.sha(self.output.read_bytes())
        (self.request() / 'events.jsonl').write_text('{}\n')
        with self.assertRaisesRegex(ValueError, 'evidence changed'): G.verify_receipt(self.output, digest)

    def test_rehashed_receipt_claim_cannot_replace_actual_reconstruction(self):
        self.run_gate()
        self.mutate(self.output, lambda d:d['executions'][0].update(prompt_id='invented'))
        with self.assertRaisesRegex(ValueError, 'differs from actual evidence'):
            G.verify_receipt(self.output, G.sha(self.output.read_bytes()))

    def test_rehashed_altered_plan_refused(self):
        envelope = json.loads(PLAN.read_text()); envelope['plan']['runtime_qualified'] = True
        envelope['plan_sha256'] = G.sha(G.canonical(envelope['plan']))
        p = self.root / 'plan.json'; self.write(p, envelope)
        with self.assertRaisesRegex(ValueError, 'Unreviewed plan'): G.load_plan(p, G.Evidence())

    def test_candidate_graph_cannot_be_reference(self):
        self.write(self.request() / 'prompt.json', self.plan['requests'][20]['graph']); self.refuse()

    def test_duplicate_prompt_id_refused(self):
        self.mutate(self.request(1) / 'submission.json', lambda d: d.update(prompt_id='synthetic-0')); self.refuse()

    def test_cached_node_refused(self):
        for file in ['history.json', 'result.json']:
            self.mutate(self.request() / file, lambda d: d['status']['messages'][1][1].update(nodes=['344']))
        self.refuse()

    def test_missing_actual_decode_event_refused(self):
        p = self.request() / 'events.jsonl'
        p.write_text(''.join(line+'\n' for line in p.read_text().splitlines() if json.loads(line)['data'].get('node') != '374'))
        self.refuse()

    def test_overlapping_reordered_timestamps_refused(self):
        for file in ['history.json','result.json']:
            self.mutate(self.request(1) / file, lambda d:d['status']['messages'][0][1].update(timestamp=1101))
        self.refuse()

    def test_native_before_optimized_and_queue_refusal(self):
        state = self.root / 'after_native.json'
        self.mutate(state, lambda d:d.update(sampler_routes=48))
        self.contract['after_native']['sha256'] = G.sha(state.read_bytes()); self.write_contract(); self.refuse()

    def test_unbound_contract_or_changed_runtime_refused(self):
        self.contract_hash = '0'*64; self.refuse()
        self.write_contract()
        self.mutate(self.request(2) / 'identity.json', lambda d:d.update(source_commit='other'))
        self.refuse()

    def test_coherently_changed_model_still_refuses_fixed_native_basis(self):
        self.contract['model_verification_sha256'] = 'c' * 64
        self.mutate(self.server / 'server-identity.json', lambda d:d.update(model_verification_sha256='c'*64))
        self.contract['server_identity_sha256'] = G.sha((self.server / 'server-identity.json').read_bytes())
        self.write_contract()
        with self.assertRaisesRegex(ValueError, 'Source/model binding differs'):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def test_conditioning_wrong_index_or_speculation_refused(self):
        p = self.server / ('pipeline-' + self.plan['requests'][0]['name'] + '.json')
        self.mutate(p, lambda d:d['detail'].update(speculation_miss=True)); self.refuse()

    def test_conditioning_tag_matches_exact_pinned_producer(self):
        parent=Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b')
        manifest_raw=G.read_file(parent/'manifest.json')
        self.assertEqual(G.sha(manifest_raw),G.PARENT_SHA)
        source=G.read_file(parent/'source/scripts/pipeline_node.py')
        self.assertEqual(G.sha(source),json.loads(manifest_raw)['files']['source/scripts/pipeline_node.py'])
        tree=ast.parse(source)
        functions=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name in ('_text_sha256','_job_tag')]
        self.assertEqual(len(functions),2)
        ns={'hashlib':hashlib}
        exec(compile(ast.Module(body=functions,type_ignores=[]),'pinned-producer-tag','exec'),ns)
        for row in self.plan['requests'][:20]:
            inputs=row['graph']['364']['inputs']
            expected=ns['_job_tag'](inputs['mode'],inputs['text'])
            report=json.loads((self.server/('pipeline-'+row['name']+'.json')).read_text())
            self.assertEqual(report['detail']['tag'],expected)
            self.assertEqual(report['detail']['text_sha256'],expected)
            self.assertNotEqual(expected,ns['_text_sha256'](inputs['text']))
        self.run_gate()

    def test_raw_text_digest_cannot_stand_in_for_window_job_tag(self):
        row=self.plan['requests'][0]
        raw_digest=G.sha(row['graph']['364']['inputs']['text'].encode('utf-8'))
        p=self.server/('pipeline-'+row['name']+'.json')
        self.mutate(p,lambda d:d['detail'].update(tag=raw_digest,text_sha256=raw_digest))
        with self.assertRaisesRegex(ValueError,'conditioning/ahead'):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def test_raw_hash_corruption_and_nonfinite_tensor_refused(self):
        p = self.root/'output/validation'/self.plan['requests'][0]['name']/'tensors.safetensors'
        raw=p.read_bytes(); p.write_bytes(raw[:-4]+struct.pack('<f',float('nan'))); self.refuse()

    def test_tenth_repeat_difference_even_coherent_summary_refused(self):
        d=self.root/'output/validation'/self.plan['requests'][19]['name']; p=d/'tensors.safetensors'
        raw=p.read_bytes(); p.write_bytes(raw[:-8]+struct.pack('<ff',7.,1.))
        self.mutate(d/'summary.json', lambda v:v['tensors']['waveform'].update(sha256=G.sha(struct.pack('<ff',7.,1.))))
        self.refuse()

    def test_tenth_first_pass_fixture_corruption_refused(self):
        folder = self.root / 'output/validation' / self.plan['requests'][9]['name']
        p = folder / 'tensors.safetensors'
        p.write_bytes(p.read_bytes()[:-4] + struct.pack('<f', float('nan')))
        with self.assertRaisesRegex(ValueError, 'Nonfinite tensor bytes'):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def test_twentieth_reference_request_is_required(self):
        (self.request(19) / 'events.jsonl').unlink()
        self.refuse()

    def test_full_fixture_phase_counts_and_fixture_mapping_are_fixed(self):
        for mutate in (lambda p: p['requests'].pop(),
                       lambda p: p['fixtures'].reverse(),
                       lambda p: p['requests'].__setitem__(slice(20,48), p['requests'][34:48]+p['requests'][20:34]),
                       lambda p: p['reference_names'].update(bird=p['reference_names']['boat'])):
            plan = copy.deepcopy(self.plan)
            mutate(plan)
            with self.assertRaises(ValueError):
                G.request_groups(plan)

    def test_timed_diagnostic_fields_absent_and_scope_required_for_every_fill_and_output(self):
        for index in (34, 38, 47):
            for key, value in [('trace_enabled', True), ('trace_enabled', 0),
                               ('trace_enabled', None), ('timing_scope', 'sampler-driver-accounting')]:
                plan = copy.deepcopy(self.plan); plan['requests'][index][key] = value
                with self.subTest(index=index, key=key, value=value), self.assertRaisesRegex(ValueError, 'without diagnostics'):
                    G.request_groups(plan)

    def test_shape_and_missing_tensor_refused(self):
        p=self.root/'output/validation'/self.plan['requests'][0]['name']/'summary.json'
        self.mutate(p, lambda v:v['tensors'].pop('waveform')); self.refuse()

    def test_fault_symlink_and_duplicate_json_refused(self):
        f=self.root/'FAULT.json'; f.write_text('{}'); self.refuse(); f.unlink()
        source=self.request()/'prompt.json'; moved=source.with_suffix('.real'); source.rename(moved); source.symlink_to(moved)
        self.refuse()
        with self.assertRaisesRegex(ValueError,'Duplicate'):G.strict_json('{"x":1,"x":2}')

    def test_native_pipeline_refuses_missing_or_old_frame_count(self):
        p = self.server / ('pipeline-' + self.plan['requests'][0]['name'] + '.json')
        original = json.loads(p.read_text())
        for bad in (None, 25, 49.0, True):
            with self.subTest(frame_count=bad):
                changed = copy.deepcopy(original)
                if bad is None:
                    changed.pop('frame_count')
                else:
                    changed['frame_count'] = bad
                self.write(p, changed)
                with self.assertRaises(ValueError):
                    self.run_gate()
                self.assertFalse(self.output.exists())
        self.write(p, original)

    def test_session_halt_refuses_otherwise_complete_native_evidence(self):
        (self.server / 'resolution-halt.json').write_text('{"reason":"postcheck failed"}')
        with self.assertRaisesRegex(ValueError, 'session halted'):
            self.run_gate()
        self.assertFalse(self.output.exists())

    def test_session_halt_appearing_at_final_recheck_prevents_receipt(self):
        original = G.Evidence.recheck
        def stop_after_read(evidence):
            original(evidence)
            (self.server / 'resolution-halt.json').write_text('{}')
        with patch.object(G.Evidence, 'recheck', stop_after_read):
            with self.assertRaisesRegex(ValueError, 'session halt before'):
                self.run_gate()
        self.assertFalse(self.output.exists())


class RealShapeContractTests(unittest.TestCase):
    def test_actual_plan49_shapes_payload_and_reader_limit(self):
        import math
        plan = json.loads(PLAN.read_text())['plan']
        self.assertEqual(G.SHAPES, plan['expected_shapes'])
        self.assertEqual(sum(math.prod(v)*4 for v in G.SHAPES.values()), 146164992)
        self.assertEqual(G.MAX_FILE_BYTES, 160*1024**2)
        self.assertLess(146164992 + 65536 + 8, G.MAX_FILE_BYTES)

    def test_old25_frame_tensor_header_refused_before_payload(self):
        header = {key: {'dtype': 'F32', 'shape': shape, 'data_offsets': [0,0]}
                  for key, shape in G.SHAPES.items()}
        header['images']['shape'] = [25,384,640,3]
        encoded = json.dumps(header).encode()
        with self.assertRaisesRegex(ValueError, 'Tensor shape differs'):
            G.tensor_inventory(struct.pack('<Q', len(encoded)) + encoded,
                               {key:{} for key in G.SHAPES})

    def test_oversized_file_refused_before_read(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'sparse-too-large.safetensors'
            with path.open('wb') as stream:
                stream.truncate(G.MAX_FILE_BYTES + 1)
            with self.assertRaisesRegex(ValueError, 'oversized evidence'):
                G.read_file(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
