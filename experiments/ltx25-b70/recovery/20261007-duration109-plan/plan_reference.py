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
ORIGINAL_IDS = ('boat', 'marble', 'bird', 'pendulum', 'rain', 'paper', 'candle', 'pour', 'fabric', 'wheel')
IDS = ('boat', 'marble', 'bird')  # explicit pilot subset, never full-suite qualification
PREFIX = 'resolution-duration109-20261007'
INDEX_BASE = 99909000  # proposed reservation; coordinator must check collisions before execution
COMPARISON_MODE = 'same-size-native-v1'
PREDECESSOR = PACKET.parent / 'prepared-duration-pilot-108b'
PREDECESSOR_SHA = 'ef839f83eaea6526f09cc353c6996a56414a95beb41609278b4b6e2994697ad7'

PREDECESSOR_CLOSEOUT = LANE / 'data/resume-20261007/duration108b-closeout/summary.json'
PREDECESSOR_CLOSEOUT_SHA = 'cf934bc6f7ddf193d14cac512acb29dbf922b2b57908b32128df4f96a562bf49'
PLACEMENT_PACKET = PACKET.parent / 'prepared-encoder-rebalance-100b'
PLACEMENT_SHA = '50beee86e0ea22d7ef2405dcb4af56631a6eab7258c4052fbfb06214381aef63'
PLACEMENT_CLOSEOUT = LANE / 'data/resume-20261007/closeout-100b.json'
PLACEMENT_CLOSEOUT_SHA = '6a06e1126b6f103bb50812308d8d26f2748e98b237c596149fa85650a7360762'
FRAMES = 49
FULL_CAPTURE_BYTES = 146164992


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
    require(digest(regular(PREDECESSOR / 'manifest.json')) == PREDECESSOR_SHA, 'Source108b predecessor differs')
    proof_raw = regular(PREDECESSOR_CLOSEOUT)
    require(digest(proof_raw) == PREDECESSOR_CLOSEOUT_SHA, 'Predecessor proof changed')
    proof = strict_json(proof_raw)
    require(proof['schema'] == 'ltx.duration108b.resource-refusal.v1' and proof['passed'] is False and
            proof['runtime_manifest_sha256'] == PREDECESSOR_SHA and proof['raw49_archives'] == 0,
            'Source108b refusal history differs')
    require(digest(regular(PLACEMENT_PACKET / 'manifest.json')) == PLACEMENT_SHA, 'Placement100b manifest differs')
    closeout_raw = regular(PLACEMENT_CLOSEOUT)
    require(digest(closeout_raw) == PLACEMENT_CLOSEOUT_SHA, 'Placement100b closeout differs')
    closeout = strict_json(closeout_raw)
    require(closeout['packet_manifest_sha256'] == PLACEMENT_SHA and
            closeout['status'] == 'completed-exact-screen-clean-stop-not-adopted' and
            closeout['quality']['total_four_tensor_exact_clips'] == 128 and
            closeout['quality']['all_parity_receipts_passed'] is True, 'Placement small-shape evidence differs')
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
    require(tuple(x['id'] for x in rows) == ORIGINAL_IDS, 'Original fixture ordering differs')
    selected = [{k: row[k] for k in ('id', 'prompt', 'seed', 'window')} for row in rows if row['id'] in IDS]
    require(tuple(row['id'] for row in selected) == IDS, 'Pilot fixture selection differs')
    require(all(row['window'] == 64 for row in selected), 'Expected accepted window64 fixtures')
    return graphs, selected


def bind_geometry(graph, qualification_id):
    graph['356']['inputs'].update(width=320, height=192, length=FRAMES, batch_size=1)
    graph['366']['inputs'].update(frames_number=FRAMES, frame_rate=24.0)
    require(graph['365']['inputs']['frame_rate'] == 24.0, 'Playback rate differs')
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
             'layout': 'two-way20-28', 'blocks': [20, 28], 'comparison_mode': COMPARISON_MODE,
             'duration_pilot': {'frames': FRAMES, 'playback_fps': 24, 'steps': [8,3],
                 'arithmetic': 'unchanged49-frame operations; only sampler layer ownership changes23/25 to20/28; fresh native references required',
                 'client_checkpoint_policy': 'storage-change-only',
                 'predecessor_manifest_sha256': PREDECESSOR_SHA,
                 'predecessor_closeout_sha256': PREDECESSOR_CLOSEOUT_SHA,
                 'predecessor_status': 'resource-refusal-before-any49-frame-output',
                 'placement_basis': {'manifest_sha256': PLACEMENT_SHA, 'closeout_sha256': PLACEMENT_CLOSEOUT_SHA,
                     'scope': '256x256/25-frame exact screen only; no49-frame quality transfer'},
                 'memory_admission': {'cards': ['xpu:0','xpu:1','xpu:2','xpu:3'],
                     'native_pre_gib': [8,8,2,9], 'capture_pre_gib': [7,7,2,9],
                     'decode_pre_gib': [2,2,10,9], 'replica_after_build_gib': 8, 'post_request_floor_gib': 2,
                     'claim': 'Unchanged engineering allowances; no measured49-frame global peak guarantee'},
                 'diagnostics': 'none', 'fixture_scope': 'three-fixture pilot only'}}
    require(tuple(f['id'] for f in fixtures) == IDS, 'Pilot fixture order differs')


    qualification_id = digest(canonical(basis))
    native = reference_template(graphs, qualification_id)
    optimized = bind_geometry(copy.deepcopy(graphs['optimized']), qualification_id)
    requests, reference_names, comparisons = [], {}, []
    for pass_no in (1, 2):
        for i, fixture in enumerate(fixtures):
            name = f'{PREFIX}-native-p{pass_no}-{fixture["id"]}'
            if pass_no == 1:
                reference_names[fixture['id']] = name
            graph = request_graph(native, fixture, name, INDEX_BASE + (pass_no - 1) * len(IDS) + i)
            requests.append({'name': name, 'phase': 'native-reference' if pass_no == 1 else 'native-repeat',
                             'fixture': fixture['id'], 'clip_index': INDEX_BASE + (pass_no - 1) * len(IDS) + i,
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
    for label, emitted_count, offset in [('candidate-check', 3, 100), ('timed-fast', 3, 200)]:
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
                requests[-1]['timing_scope'] = 'unscored-fill' if emitted < 0 else 'duration49-three-fixture-pilot'
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
                'adopted_policy': 'storage-change-only for the uninstrumented timed block; preserve all explicit mutation saves and event fsyncs; no client comparison',
                'always_required': ['all source/hash verification', 'fault/halt checks',
                    'fresh free-space checks and write-budget accounting',
                    'every mutated ledger durable before its dependent action',
                    'request-attempt and completion durability', 'event log flush/fsync'],
                'required_readout': 'Successor must retain source-bound client-policy.json identifying actual policy and checkpoint/save/skip counts for each timed request.',
                'readout_implemented': False},
            'timing_scopes': [
                {'scope': scope, 'phase': phase, 'client_checkpoint_policy': policy,
                 'emitted_indices': list(range(3)), 'completion_interval_count': 2,
                 'request_names': [r['name'] for r in requests if r.get('timing_scope') == scope],
                 'claim': 'Three ordered fixtures, only two completion intervals; no adoption, full-suite, gain, endurance, or record claim.'}
                for scope, phase, policy in [('duration49-three-fixture-pilot','timed-fast','storage-change-only')]],
            'execution_preconditions': ['108b immutable source and refusal history plus100b small-shape placement evidence remain pinned',
                'new immutable20/28 duration-specific runtime; never extend consumed108b admission; runtime must select exact named placement',
                'fresh 4GiB storage admission above50GiB floor with prewrite classification and category caps',
                'first-native header/memory barrier passes before any subsequent model request',
                'same-length native repeats, chain checks and replica checks; no tracing or passive collector'],
            'first_native_barrier': {'after_request': requests[0]['name'],
                'before_request': requests[1]['name'], 'action': 'verify-first-native',
                'requires': ['actual four tensor shapes/dtypes/finite payloads equal the pinned49-frame contract',
                    'native resident ownership unchanged and no fallback/eviction/fault',
                    'per-card allocation peaks and physical-free observations reviewed',
                    'post-native physical free at least2GiB on every card',
                    'durable source-bound receipt before second request'], 'implemented': False},
            'pipeline_depths': {'sampler': sampler_depth, 'decode': decode_depth},
            'expected_shapes': {'images': [49,384,640,3], 'video_latent': [1,128,7,12,20],
                                'audio_latent': [1,8,51,16], 'waveform': [1,2,96480]},
            'lifecycle': ['same-server-window-probe', 'first-native-header-memory-barrier',
                          'serial-six-native-executions-three-repeat-comparisons',
                          'capture-and-qualify-both-workers-two-duration-specific-shapes',
                          'candidate-check-three-emitted-exact', 'quiescence-with-no-cross-phase-pending-jobs',
                          'timed-fast-three-emitted-exact-two-intervals',
                          'quiescence-and-preserve-successful-application'],
            'pending': ['reviewed immutable runtime/source closure and collision admission',
                        'duration49 geometry, audio, waveform and graph-signature guards',
                        'actual20/28 ownership and native/capture/replica memory admission with unchanged engineering floors',
                        'first-native gate and independently reconstructed six-native/four-tensor proof',
                        'prewrite capture categories, category byte limits, free-space and cache growth enforcement',
                        'fault-halt no-retry client, phase quiescence and completed-tail retirement'],
            'proposed_storage_policy': {
                'max_total_captures': 22, 'planned_write_bytes': 4*1024**3,
                'min_free_bytes': 50*1024**3, 'enforced': False,
                'four_tensor_fp32_bytes_per_clip': FULL_CAPTURE_BYTES,
                'full_output_equivalent_cap': 14, 'placeholder_cap': 8,
                'placeholder_max_bytes': 1024**2, 'archive_header_max_bytes': 65544,
                'cache_max_bytes': 1024**3, 'preview_max_bytes': 512*1024**2,
                'logs_metadata_headers_max_bytes': 192*1024**2,
                'total_bound_bytes': 14*(FULL_CAPTURE_BYTES + 65544) + 8*1024**2 + 1024**3 + 512*1024**2 + 192*1024**2,
                'capture_classification': {
                    'full_output_equivalent_request_names': [r['name'] for r in requests
                        if r['phase'] in ('native-reference','native-repeat') or r['expected_emitted_index'] is not None]
                        + [PREFIX+'-capture0',PREFIX+'-capture1'],
                    'placeholder_request_names': [r['name'] for r in requests
                        if r['phase'] in ('candidate-check','timed-fast') and r['expected_emitted_index'] is None],
                    'note': '22 actual capture graphs:14 full-equivalent including both setup captures conservatively;8 optimized fill placeholders; no extra requests'},
                'required_prewrite_checks': [
                    'exact admitted request and exclusive owned destination; count every capture graph including fills',
                    'derive actual tensor shape/dtype/byte sizes and bounded header BEFORE opening/writing archive',
                    'placeholder whole archive at most1MiB; full payload at most146164992bytes and header including prefix at most65544bytes',
                    'atomically charge capture/category/total bytes and remaining allowance before any write',
                    'reject unexpected full-size placeholder or excess category; never truncate, omit tensors, suppress outputs or reroute',
                    'bound preview/log/metadata/header/cache writes and check fresh free space above50GiB plus unspent allowance',
                    'halt new requests on budget/fault; no automatic cleanup/retry'],
                'extra_request_or_hidden_output_suppression': False},
            'native_encoder_contract': {'method': 'run_ahead collects current index/tag, never prior clip',
                                        'depth': 2, 'serial_submission_only': True,
                                        'require_empty_prompt_queue': True, 'require_started_ahead_empty': True,
                                        'require_speculation_miss_false': True},
            'claim_limit': 'Three-fixture49-frame640x384 qualification pilot against fresh same-length native sampler/decode references with accepted graph-sharded window encoder. Two timing intervals only; no adoption, full-suite, speed-gain, visual-quality, endurance, all-eager, larger-resolution or record claim.'}



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
