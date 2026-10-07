#!/usr/bin/env python3
"""CPU-only deterministic graph/qualification plan. No network, models or runtime build."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import stat
import sys

HERE = Path(__file__).resolve().parent
LANE = HERE.parents[1]
PACKET = Path('/mnt/fast-ai/bench-results/ltx25-baseline-20260913/prepared-encoder-upstream-99b')
MANIFEST_SHA = 'f819270165a7e8c59206b0dd641ebb1b7763e586b458a1e32a75344f96220d0a'
FIXTURES = LANE / 'data/stability-01-window-prereg.json'
FIXTURES_SHA = '9c188d9b96805ec1cfc3e6c694f952550ebfd8166a9a11c23044cb14834abb17'
GRAPH_FILES = {
    'native': 'graphs/host-embedding-control.json',
    'optimized': 'graphs/graph-capture-all48-pipe-samp2-tsh-rep-wlean-s1.json',
    'window_probe': 'graphs/text-window-probe.json',
}
GRAPH_SHAS = {
    'native': 'bee894d8e03cf4b73a7e93114ed7a0b586670da0ccd33a9acfd20ff868999497',
    'optimized': '3d0f1c0c3ecb812971b690fec7efb882552b9ed37ff24b262937f2b28749eae4',
    'window_probe': 'ce6085a42aab926e8159c9bc966cc1b67a8da03dd6ecaef6b5efa52669ccd7a0',
}
IDS = ('boat', 'marble', 'bird', 'pendulum', 'rain', 'paper', 'candle', 'pour', 'fabric', 'wheel')  # complete original ordered suite
PREFIX = 'resolution-sampler-accounting-20261007'
INDEX_BASE = 99906000  # proposed reservation; coordinator must check collisions before execution
COMPARISON_MODE = 'same-size-native-v1'
PREDECESSOR = PACKET.parent / 'prepared-client-reverse-105'
PREDECESSOR_SHA = '1ff7bd5ab281dad1a19f8d01aaf8899505168f0606689ba43ccb23cc05311fad'


def require(ok, why):
    if not ok:
        raise ValueError(why)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, value in rows:
            require(key not in result, 'Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def regular(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe source path')
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_size <= 4 * 1024**2, 'Nonregular/oversized source')
    raw = path.read_bytes(); after = path.stat()
    require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), 'Source changed during read')
    return raw


def load_inputs(packet=PACKET, fixtures=FIXTURES):
    require(digest(regular(PREDECESSOR / 'manifest.json')) == PREDECESSOR_SHA, 'Qualified105 predecessor differs')
    raw = regular(packet / 'manifest.json')
    require(digest(raw) == MANIFEST_SHA, 'Qualified99b manifest differs')
    manifest = strict_json(raw)
    graphs = {}
    for role, name in GRAPH_FILES.items():
        raw = regular(packet / name)
        require(digest(raw) == GRAPH_SHAS[role] == manifest['files'][name], 'Pinned graph differs: ' + role)
        graphs[role] = strict_json(raw)
    raw = regular(fixtures)
    require(digest(raw) == FIXTURES_SHA, 'Accepted fixture packet differs')
    rows = strict_json(raw)['fixtures']
    require(tuple(x['id'] for x in rows) == IDS, 'Original fixture ordering differs')
    selected = [{k: row[k] for k in ('id', 'prompt', 'seed', 'window')} for row in rows]
    require(all(row['window'] == 64 for row in selected), 'Expected accepted window64 fixtures')
    return graphs, selected


def bind_geometry(graph, qualification_id):
    graph['356']['inputs'].update(width=320, height=192, length=25, batch_size=1)
    # These new optional fields are a proposed runtime contract, NOT currently executable.
    for node in ('364', '428', '426'):
        if node in graph:
            graph[node]['inputs'].update(output_size='640x384', speed_only=False,
                                         comparison_mode=COMPARISON_MODE, qualification_id=qualification_id)
    return graph


def reference_template(graphs, qualification_id):
    graph = copy.deepcopy(graphs['native'])
    # Share only the accepted text-encoding workload, not candidate sampling/decode.
    graph['425'] = copy.deepcopy(graphs['optimized']['425'])
    graph['364'] = copy.deepcopy(graphs['optimized']['364'])
    graph['365']['inputs'].update(positive=['364', 0], negative=['364', 0])
    del graph['421']
    # Exact raw capture remains; optional lossy preview is not needed for oracle creation.
    del graph['75'], graph['370']
    return bind_geometry(graph, qualification_id)


def request_graph(template, fixture, name, index):
    graph = copy.deepcopy(template)
    for node in graph.values():
        fields = node['inputs']
        if 'run_name' in fields:
            fields['run_name'] = name
        if isinstance(fields.get('clip_index'), int):
            fields['clip_index'] = index
    graph['364']['inputs']['text'] = fixture['prompt']
    for node in ('338', '339'):
        graph[node]['inputs']['noise_seed'] = fixture['seed']
    return graph


def validate_graph_edges(graph):
    require(isinstance(graph, dict) and graph, 'Empty graph')
    for key, node in graph.items():
        require(isinstance(key, str) and key.isdecimal(), 'Bad node ID')
        require(set(node) == {'class_type', 'inputs'}, 'Unexpected node fields')
        for value in node['inputs'].values():
            if isinstance(value, list):
                require(len(value) == 2 and value[0] in graph and type(value[1]) is int and value[1] >= 0,
                        'Dangling/malformed graph edge')
    visiting, done = set(), set()
    def visit(key):
        require(key not in visiting, 'Graph cycle')
        if key in done:
            return
        visiting.add(key)
        for value in graph[key]['inputs'].values():
            if isinstance(value, list):
                visit(value[0])
        visiting.remove(key); done.add(key)
    for key in graph:
        visit(key)


def build_plan(graphs, fixtures):
    basis = {'schema': 'ltx.same-size-reference-basis.v1', 'parent_manifest_sha256': MANIFEST_SHA,
             'graph_sha256': GRAPH_SHAS, 'fixtures_sha256': FIXTURES_SHA,
             'fixture_ids': list(IDS), 'size': '640x384', 'batch': 1, 'sampler_workers': 2,
             'layout': 'two-way', 'blocks': [23, 25], 'comparison_mode': COMPARISON_MODE,
             'sampler_accounting': {
                 'numerical_change': False, 'client_checkpoint_policy': 'storage-change-only',
                 'timing_order': ['timed-fast'], 'predecessor_manifest_sha256': PREDECESSOR_SHA,
                 'scope': 'bounded raw per-client per-engine proc fdinfo accounting only',
                 'engines': ['ccs', 'bcs'], 'gpu_instrumentation': False,
                 'uuid_mapping_assumed': False, 'utilization_headline': False}}

    qualification_id = digest(canonical(basis))
    native = reference_template(graphs, qualification_id)
    optimized = bind_geometry(copy.deepcopy(graphs['optimized']), qualification_id)
    requests, reference_names, comparisons = [], {}, []
    for pass_no in (1, 2):
        for i, fixture in enumerate(fixtures):
            name = f'{PREFIX}-native-p{pass_no}-{fixture["id"]}'
            if pass_no == 1:
                reference_names[fixture['id']] = name
            graph = request_graph(native, fixture, name, INDEX_BASE + (pass_no - 1) * 10 + i)
            requests.append({'name': name, 'phase': 'native-reference' if pass_no == 1 else 'native-repeat',
                             'fixture': fixture['id'], 'clip_index': INDEX_BASE + (pass_no - 1) * 10 + i,
                             'graph': graph, 'graph_sha256': digest(canonical(graph)),
                             'client_checkpoint_policy': 'always',
                             'execution': 'serial-complete-before-next-request'})
            if pass_no == 2:
                comparisons.append({'phase': 'reference-repeat', 'reference': reference_names[fixture['id']],
                                    'candidate': name, 'fixture': fixture['id']})
    optimized['428']['inputs']['depth'] = 2
    sampler_depth = optimized['428']['inputs']['depth']
    decode_depth = optimized['426']['inputs']['depth']
    require(sampler_depth == 2 and decode_depth == 2, 'Reviewed W2 optimized pipeline depth changed')
    phases = []
    for label, emitted_count, offset in [('candidate-check', 10, 100), ('timed-fast', 10, 200)]:
        start = len(requests); submitted_count = emitted_count + sampler_depth + decode_depth
        for i in range(submitted_count):
            fixture = fixtures[i % len(fixtures)]; name = f'{PREFIX}-{label}-{i:02d}'
            graph = request_graph(optimized, fixture, name, INDEX_BASE + offset + i)
            emitted = i - sampler_depth - decode_depth
            target = fixtures[emitted % len(fixtures)] if emitted >= 0 else None
            requests.append({'name': name, 'phase': label, 'fixture': fixture['id'],
                             'clip_index': INDEX_BASE + offset + i,
                             'graph': graph, 'graph_sha256': digest(canonical(graph)),
                             'expected_emitted_index': emitted if emitted >= 0 else None,
                             'expected_emitted_fixture': None if target is None else target['id'],
                             'reference': None if target is None else reference_names[target['id']],
                             'client_checkpoint_policy': 'storage-change-only' if label == 'timed-fast' else 'always',
                             'execution': 'bounded-pipeline-with-explicit-phase-quiescence'})
            if label == 'timed-fast':
                requests[-1]['timing_scope'] = 'unscored-fill' if emitted < 0 else 'sampler-driver-accounting'
            if target is not None:
                comparisons.append({'phase': label, 'reference': reference_names[target['id']],
                                    'candidate': name, 'fixture': target['id']})
        phases.append({'phase': label, 'submitted': submitted_count, 'emitted': emitted_count,
                       'pipeline_fills': sampler_depth + decode_depth,
                       'request_names': [r['name'] for r in requests[start:]]})
    for row in requests:
        validate_graph_edges(row['graph'])
    require(len({r['name'] for r in requests}) == len(requests), 'Duplicate request name')
    require(len({r['clip_index'] for r in requests}) == len(requests), 'Duplicate clip index')
    require(all(0 <= r['clip_index'] <= 100000000 for r in requests), 'Clip index ceiling')
    return {'schema': 'ltx.resolution-reference-plan.v1', 'status': 'CPU-DESIGN-NOT-RUNTIME-READY',
            'runtime_qualified': False, 'model_requests': 0, 'qualification_id': qualification_id,
            'basis': basis, 'fixtures': fixtures, 'reference_names': reference_names,
            'comparison_tensors': ['images', 'video_latent', 'audio_latent', 'waveform'],
            'requests': requests, 'comparisons': comparisons, 'optimized_phases': phases,
            'client_checkpoint_contract': {
                'adopted_policy': 'storage-change-only for the diagnostic block; preserve all explicit mutation saves and event fsyncs; no client comparison',
                'always_required': ['all source/hash verification', 'fault/halt checks',
                    'fresh free-space checks and write-budget accounting',
                    'every mutated ledger durable before its dependent action',
                    'request-attempt and completion durability', 'event log flush/fsync'],
                'required_readout': 'Successor must retain source-bound client-policy.json identifying actual policy and checkpoint/save/skip counts for each timed request.',
                'readout_implemented': False},
            'timing_scopes': [
                {'scope': scope, 'phase': phase, 'client_checkpoint_policy': policy,
                 'emitted_indices': list(range(10)),
                 'request_names': [r['name'] for r in requests if r.get('timing_scope') == scope],
                 'claim': 'One complete ordered ten-fixture block within one application; repeated-workload screen, not a cold-request measurement, headline, or record.'}
                for scope, phase, policy in [('sampler-driver-accounting','timed-fast','storage-change-only')]],
            'accounting_contract': {
                'status': 'pending-independent-collector-review-and-runtime-admission',
                'mode': 'read-only-existing-render-fdinfo', 'engines': ['ccs', 'bcs'],
                'interval_seconds': 2, 'duration_seconds': 120, 'max_samples': 64,
                'max_output_bytes': 128 * 1024,
                'required_bindings': ['collector-source', 'contract', 'plan', 'server-identity',
                    'PID-start-ticks-boot', 'exact-render-node-to-PCI-evidence'],
                'required_behavior': ['before-and-after-process-source-fault-checks',
                    'bounded-descriptor-task-read-coverage', 'deduplicate-same-DRM-client',
                    'retain-distinct-clients-and-own-engine-denominators',
                    'missing-or-changed-coverage-explicitly-incomplete',
                    'busy-regression-retains-high-watermark-not-hardware-fault',
                    'no-device-opens-no-GPU-calls-no-endpoints-no-signals',
                    'raw-counters-only-no-aggregate-utilization-or-idle-inference'],
                'does_not_authorize_105_extension': True, 'implemented_here': False},
            'execution_preconditions': ['105 native, candidate, fast and final control exact output gates all pass',
                'fresh storage admission for 4GiB writes above 50GiB reserve',
                'reviewed successor retains reduced-write policy and source-bound readouts',
                'independently reviewed bounded collector with admitted process/device/source coverage'],
            'pipeline_depths': {'sampler': sampler_depth, 'decode': decode_depth},
            'expected_shapes': {'images': [25,384,640,3], 'video_latent': [1,128,4,12,20],
                                'audio_latent': [1,8,26,16], 'waveform': [1,2,48480]},
            'lifecycle': ['same-server-window-probe', 'serial-native-reference-and-repeat',
                          'verify-twenty-executions-and-ten-four-tensor-repeat-comparisons',
                          'capture-and-qualify-optimized-path', 'candidate-check-ten-emitted-exact',
                          'quiescence-with-no-cross-phase-pending-jobs', 'timed-fast-ten-emitted-with-bounded-passive-accounting-verify-parity-and-retire-tails',
                          'quiescence-and-preserve-successful-application-for-authorized-follow-up'],
            'pending': ['reviewed immutable runtime successor and complete source/dependency closure',
                        'new exact plan admission; existing105 schedule cannot admit106 requests',
                        'same-size native transient plus later graph-pool memory admission',
                        'same-size replica and whole-chain gates',
                        'fault-halt no-retry live client; execution identities and no-cached-node checks',
                        'phase quiescence/reset contract for monotonic clip indices; no stale queued conditioning',
                        'pre-native residency/physical-free gate and explicit OOM-to-tiled-decode refusal',
                        'enforce exact capture cap50 including setup/repeats/queued tails; 4GiB allowance conditional on fresh storage admission',
                        'reserved request names/clip-index collision check before execution',
                        'bounded disk admission and reviewed reference retention'],
            'proposed_storage_policy': {'max_total_captures': 50, 'planned_write_bytes': 4 * 1024**3,
                                        'min_free_bytes': 50 * 1024**3, 'enforced': False,
                                        'four_tensor_fp32_bytes_per_clip': 74620672},
            'native_encoder_contract': {'method': 'run_ahead collects current index/tag, never prior clip',
                                        'depth': 2, 'serial_submission_only': True,
                                        'require_empty_prompt_queue': True, 'require_started_ahead_empty': True,
                                        'require_speculation_miss_false': True},
            'claim_limit': 'Complete original ten-fixture same-size native-sampler/decode exactness with accepted graph-sharded window encoder, plus bounded passive raw driver-accounting diagnostics with the adopted reduced-write client policy; no further client comparison or inferred device-idle/aggregate-utilization claim; repeated-workload screen, no all-eager, broad visual-quality, longer-video, endurance, cold-request, performance-headline, or record claim.'}


def envelope(plan):
    return {'plan': plan, 'plan_sha256': digest(canonical(plan))}


def validate_envelope(value, expected_plan):
    require(set(value) == {'plan', 'plan_sha256'}, 'Unexpected plan envelope')
    require(re.fullmatch('[0-9a-f]{64}', value['plan_sha256'] or '') is not None and
            value['plan_sha256'] == digest(canonical(value['plan'])), 'Plan hash differs')
    # Reconstruct from pinned independent inputs, not just a self-supplied digest.
    require(canonical(value['plan']) == canonical(expected_plan), 'Plan differs from exact pinned construction')
    return {'status': 'CPU-plan-valid-runtime-pending', 'plan_sha256': value['plan_sha256'],
            'requests_planned': len(expected_plan['requests']), 'model_requests': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('plan', 'validate'))
    parser.add_argument('--plan-file', type=Path)
    args = parser.parse_args()
    graphs, fixtures = load_inputs(); plan = build_plan(graphs, fixtures)
    if args.command == 'validate':
        require(args.plan_file is not None, '--plan-file required')
        result = validate_envelope(strict_json(regular(args.plan_file.absolute())), plan)
    else:
        require(args.plan_file is None, 'plan emits stdout only; does not write runtime artifacts')
        result = envelope(plan)
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))


if __name__ == '__main__':
    main()
