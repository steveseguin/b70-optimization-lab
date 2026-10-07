"""Inspect setup verdicts: a successful Comfy request alone is insufficient.

All functions are CPU-only and consume newly written source-bound receipts.
These internal checks do not substitute for native/candidate four-tensor parity.
"""
import math
import re

MODEL_SHA = '273ad9125c1cbe239e44ffaa29ce11a7eb8f89d252630de7ef8e6503a1c1cf0f'
GIB = 2**30


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def bound(report, name, identity_sha):
    require(report['run_name'] == name and report['server_identity_sha256'] == identity_sha and
            report['model_verification_sha256'] == MODEL_SHA and report['output_size'] == '640x384',
            'Setup receipt identity/model/size differs')


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_window(report, name, identity_sha):
    bound(report, name, identity_sha)
    require(report['schema'] == 'ltx.text-window-probe.v1' and report['passed'] is True and
            report['outcome'] == 'window-qualified', 'Text window did not qualify')
    require(report['pending_encode_at_start'] == [] and report['worker_errors'] == [] and
            report['reasons'] == [] and set(report['workers']) == {'ltx-encode-0', 'ltx-encode-1'},
            'Window probe incomplete or failed')
    require(64 in report['admitted'] and report['prompt_count'] == 40 and len(report['rows']) == 40,
            'Original window workload or bucket coverage differs')
    by_name = {row['prompt']: row for row in report['rows']}
    require(len(by_name) == 40, 'Duplicate window prompt')
    for name in ('fixture-boat', 'fixture-marble', 'fixture-bird'):
        require(by_name[name]['window'] == 64, 'Reference fixture window changed')
    for row in report['rows']:
        require(row['finite'] is True and row['full_identical_across_workers'] is True,
                'Nondeterministic/nonfinite window probe')
        hashes = row['window_sha256']
        require(len(hashes) == 4 and len(set(hashes)) == 1 and
                len(row['full_sha256']) == 2 and len(set(row['full_sha256'])) == 1,
                'Window repeat or worker outputs differ')
        for key, upper in (('mean_rel', .001), ('max_abs_in_bf16_steps', 2.), ('differing_fraction', .05)):
            require(finite_number(row[key]) and 0 <= row[key] <= upper, 'Window closeness failed: ' + key)
    for worker in (0, 1):
        capture = report['capture']['w%d/64' % worker]
        require(capture == {'captured': 48, 'error': None}, 'Window64 graph coverage incomplete')
    return {'passed': True, 'kind': 'accepted-window-consistency', 'output_parity_claimed': False}


def validate_coverage(report, name, identity_sha):
    bound(report, name, identity_sha)
    require(report['schema'] == 'ltx.sampler-capture-coverage.v2' and report['outcome'] == 'covered',
            'Sampler capture did not cover every route')
    require(report['sampler_workers'] == 2 and report['sampler_batch'] == report['sampler_shared_pool'] == 1 and
            report['signature_batches'] == [1] and report['open_batch_group'] == [] and
            report['pipeline_busy'] == report['pipeline_running'] == 0,
            'Capture worker/batch/quiescence differs')
    require(sorted(report['worker_names']) == ['ltx-sample-0', 'ltx-sample-1'],
            'Capture worker names differ')
    coverage = report['coverage']
    require(coverage['routes'] == 48 and coverage['workers'] == 2 and
            coverage['signatures_per_route_min'] == 2 and coverage['incomplete_routes'] == [],
            'Incomplete two-stage W2 graph coverage')
    return {'passed': True, 'kind': 'capture-coverage', 'output_parity_claimed': False}


def validate_freeze(report, name, identity_sha):
    bound(report, name, identity_sha)
    require(report['schema'] == 'ltx.sampler-capture-freeze.v2' and report['outcome'] == 'frozen' and
            report['frozen'] is True and report['loads_frozen'] is True,
            'Sampler/model loads were not frozen')
    require(report['placement'] == 'two-way' and report['sampler_workers'] == 2 and
            report['sampler_batch'] == 1 and report['sampler_shared_pool'] == 1 and
            report['signature_batches'] == [1] and report['residents_missing'] == [] and
            report['segment_devices'] == ['xpu:0', 'xpu:1'], 'Freeze configuration or residence differs')
    require(report['coverage'] == {'routes': 48, 'workers': 2, 'signatures_per_route_min': 2,
                                   'incomplete_routes': []}, 'Freeze coverage incomplete')
    free = report['free_bytes']
    require(set(free) == {'xpu:%d' % i for i in range(4)} and
            all(type(n) is int and n >= 2*GIB for n in free.values()) and report['floor_bytes'] == 2*GIB,
            'Actual post-chain free memory below floor')
    require(report['floor_judged_on'] == 'the reading after the chain check released its memory',
            'Freeze used pre-chain memory only')
    chain = report['chain_check']
    require(chain['chains_checked'] == chain['chains_passed'] == 4 and chain['expected_shapes'] == 2 and
            chain['shared_pool'] == 1 and len(chain['rows']) == 4, 'Whole-chain replay incomplete')
    threads = {r['thread'] for r in chain['rows']}
    pairs = {(r['device'], r['thread']) for r in chain['rows']}
    require(len(threads) == 2 and all(type(t) is int and t > 0 for t in threads) and
            pairs == {(device, thread) for device in ('xpu:0', 'xpu:1') for thread in threads} and
            len(pairs) == len(chain['rows']), 'Whole-chain worker/device set differs')
    for row in chain['rows']:
        expected_blocks = list(range(0,23)) if row['device'] == 'xpu:0' else list(range(23,48))
        shapes = sorted(row['shapes'], key=lambda s: s[0][1])
        require(row['blocks'] == expected_blocks and row['order'] == 'ABAB' and row['passed'] is True and
                row['replay_equals_eager'] == row['replay_equals_repeat'] == [True, True] and
                shapes == [[[1,240,4096],[1,26,2048]], [[1,960,4096],[1,26,2048]]],
                '640x384 stage chain is not independently exact')
    return {'passed': True, 'kind': 'same-size-graph-chain-and-residency', 'output_parity_claimed': False}


def validate_decode(report, name, identity_sha):
    bound(report, name, identity_sha)
    require(report['schema'] == 'ltx.decode-replica-probe.v1' and report['passed'] is True and
            report['outcome'] == 'replica-exact' and report['placement_checked'] is True,
            'Decode replica did not pass')
    require(report['replica_device'] == 'xpu:2' and report['native_device'] == 'xpu:3' and
            set(report['replicas_resident']) == {'audio','video'}, 'Replica ownership differs')
    require(report['references'] == 'none (speed only)', 'Unexpected internal seeded-probe identity')
    # Historical labels are preserved. These ten random latent probes establish
    # cross-card decoder consistency only; actual clips need the separate gate.
    rows = report['rows']
    require(len(rows) == 10 and {r['seed'] for r in rows} == set(range(980000,980010)),
            'Seeded decoder workload differs')
    for row in rows:
        require(row['output_size'] == '640x384' and row['video_latent_shape'] == [1,128,4,12,20] and
                row['references'] == 'none (speed only)' and
                row['passed'] is True and row['cards_bytewise_equal'] is True and
                row['replica_matches_native'] is True and row['native'] == row['replica'],
                'Seeded decoder tensors differ')
        require(set(row['native']) == {'images_sha256', 'waveform_sha256'} and
                all(isinstance(h, str) and re.fullmatch('[0-9a-f]{64}', h)
                    for h in row['native'].values()), 'Missing decoder tensor hashes')
    for suffix, minimum in (('after_build', 5*GIB), ('after_probe', 2*GIB)):
        free, method = report['xpu:2_free_' + suffix]
        require(type(free) is int and free >= minimum and method == 'mem_get_info',
                'Replica memory not admitted from actual device reading')
    require(report['vae_residency']['offending_tensors_after'] == {'AudioVAE': 0, 'CausalDiffusionVAE': 0},
            'Native VAEs not resident after replica preparation')
    return {'passed': True, 'kind': 'ten-seeded-native-vs-replica-decodes',
            'same_size_reference_comparison': False, 'output_parity_claimed': False}
