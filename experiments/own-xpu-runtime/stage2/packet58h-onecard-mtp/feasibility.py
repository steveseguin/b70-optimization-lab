#!/usr/bin/env python3
"""Metadata-only 58h feasibility; no runtime import, model read or device access."""
import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import statistics

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
STAGE = HERE.parent
GIB = 1024**3


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def capture():
    require(not (HERE / 'inputs.json').exists(), 'capture already exists')
    sources = {}
    base = STAGE / 'packet58g-onecard/evidence/card0-58g-a'
    for window in ('KD', 'WS', 'WS128x'):
        sources[window + '_window'] = base / window / 'window.json'
        sources[window + '_census'] = base / window / 'run/run/census.json'
    sources['baseline'] = base / 'WS128x/summary.json'
    sources['draft_census'] = STAGE / 'packet84-record-bundle/evidence/census.json-050df3fc86bf2a8403d7f75c97fed6c96b8a9c3a0f5925d5c5183e51df482956.gz'
    sources['draft_manifest'] = STAGE / 'packet58g-onecard/mtp-manifest.tsv'
    sources['model85'] = STAGE / 'packet85-critical-path/model.json'
    sources['restore68'] = STAGE / 'packet68-mtp-depth2/evidence/device-cost.json'
    for rank in (0, 1):
        sources[f'm2_rank{rank}'] = STAGE / f'screen/v3-packet64-lanes/evidence/packet68c-production-B-01/run/ranks/rank{rank}/batched-rows.jsonl'
    records = {}
    out = HERE / 'evidence'
    out.mkdir(exist_ok=True)
    for key, path in sources.items():
        raw = path.read_bytes()
        data = gzip.decompress(raw) if path.suffix == '.gz' else raw
        require(len(data) < 32 * 1024**2, 'unexpectedly large evidence input')
        encoded = gzip.compress(data, mtime=0)
        target = out / (sha(data) + '.gz')
        if not target.exists():
            target.write_bytes(encoded)
        records[key] = dict(source=str(path.relative_to(REPO)),
                            source_sha256=sha(raw), content_sha256=sha(data),
                            archive=str(target.relative_to(HERE)), bytes=len(data))
    source_pins = {}
    for name in ('packet58g-onecard/mtp.hpp', 'packet58g-onecard/main.cpp',
                 'packet58g-onecard/memory_plan.py', 'packet58g-onecard/cache_table.hpp',
                 'packet58g-onecard/strict_snapshot.hpp',
                 'packet71c-depth2-engine/dependent_rows.hpp'):
        path = STAGE / name
        source_pins[str(path.relative_to(REPO))] = sha(path.read_bytes())
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        if key in ('MemTotal', 'MemAvailable', 'GPUActive', 'SwapTotal', 'SwapFree'):
            mem[key] = int(value.split()[0]) * 1024
    blocks = {str(i): Path(f'/sys/devices/system/memory/memory{i}/state').read_text().strip()
              for i in range(53, 58)}
    sysmem = Path('/sys/devices/system/memory')
    offline = sorted(int(p.parent.name[6:]) for p in sysmem.glob('memory*/state')
                     if p.read_text().strip() == 'offline')
    dump(HERE / 'inputs.json', dict(schema='packet58h.inputs.v1', inputs=records,
         source_pins=source_pins, passive_snapshot=dict(host=os.uname().nodename,
         meminfo=mem, memory_blocks=blocks, offline_blocks=offline,
         memory_block_bytes=int((sysmem / 'block_size_bytes').read_text().strip(), 16),
         disk_free_bytes=shutil.disk_usage(REPO).free),
         capture_utc=datetime.now(timezone.utc).isoformat()))


def analyze():
    manifest = json.loads((HERE / 'inputs.json').read_text())

    def raw(key):
        pin = manifest['inputs'][key]
        data = gzip.decompress((HERE / pin['archive']).read_bytes())
        require(sha(data) == pin['content_sha256'], 'input changed: ' + key)
        return data.decode()

    def read(key):
        return json.loads(raw(key))

    windows = {w: read(w + '_window') for w in ('KD', 'WS', 'WS128x')}
    censuses = {w: read(w + '_census')[0] for w in windows}
    target = censuses['WS128x']
    require(all(c == target for c in censuses.values()), 'one-card census changed between windows')
    require(all(w['passed'] and w['miss_path'] == 'zero-copy' for w in windows.values()),
            'baseline identity/passed gate differs')
    require(target['totals']['device'] == 24_287_732_980, 'target census changed')
    require(next(r['bytes'] for r in target['allocations']
                 if r['label'] == 'card0:weight:output.weight') == 248_320 * 3380,
            'shared target head row layout differs')
    plan = windows['WS128x']['memory_admission']['plan']
    mutable = [r for r in target['allocations']
               if r['memory'] == 'device' and r['category'] != 'weights']
    mutable_bytes = sum(r['bytes'] for r in mutable)
    require(mutable_bytes == 471_023_348, 'target mutable inventory changed')
    draft = [r for r in read('draft_census')['allocations'] if ':draft:' in r['label']]
    weights = [r for r in draft if r['category'] == 'weights']
    groups = {}
    for row in weights:
        name = row['label']
        group = ('experts' if '_exps.weight' in name else
                 'attention_and_norms' if any(s in name for s in
                  ('attn_q', 'attn_k', 'attn_v', 'attn_output', 'indexer')) else
                 'hc_and_norms' if 'hc_' in name else
                 'input_merge_and_norms' if 'mtp.' in name else 'router_and_shared_expert')
        groups[group] = groups.get(group, 0) + row['bytes']
    require(groups['experts'] == 3 * 512 * 640 * (2560 + 2560 // 16 * 4),
            'INT8 draft expert layout differs')
    weight_bytes = sum(groups.values())
    kv = sum(r['bytes'] for r in draft if r['category'] == 'KV')
    workspace = sum(r['bytes'] for r in draft if r['category'] == 'workspace')
    pinned = sum(r['bytes'] for r in draft if r['memory'] == 'host-pinned')
    require((weight_bytes, kv, workspace, pinned) ==
            (3_326_953_472, 9_699_328, 17_711_414, 20_492), 'draft inventory differs')
    # Proposed conservative layout: canonical prefix stays untouched; two full
    # target mutable rows retain prefixes 1/2, including uncompressed KV. One
    # complete private draft image permits discard/repair. No scratch shrink.
    # Each copy table reserves 4096 x (dst, src, bytes, cumulative tiles).
    transaction = dict(target_two_private_rows=2 * mutable_bytes,
                       draft_private_image=kv + workspace,
                       target_and_draft_copy_tables=2 * 4096 * 32)
    transaction_bytes = sum(transaction.values())
    require(transaction_bytes <= plan['device_categories']['control_transaction_bound'],
            'private rows exceed unchanged transaction allowance')
    base_workspace = sum(r['bytes'] for r in mutable if r['category'] == 'workspace')
    require(base_workspace + workspace <= plan['device_categories']['workspace_bound'],
            'draft workspace exceeds unchanged workspace allowance')
    immutable_plus_kv = weight_bytes + kv
    # Dedicated allocations below are exact proposed payload bytes, not a new
    # measured census. Existing host workspace/metadata allowances cover STL
    # maps, row descriptors and two 131072-byte host copy-table vectors.
    device_extra = immutable_plus_kv + workspace + transaction_bytes
    base_required = plan['timing_required_available_bytes']
    exact_required = plan['host_required_available_bytes']
    available = {w: j['memory_admission']['available_bytes'] for w, j in windows.items()}
    shadow = max(j['postload_memory']['peak_shadow_bytes'] for j in windows.values())
    options = {}
    for cached in (False, True):
        label = 'shared_cache_draft_experts' if cached else 'resident_draft_experts'
        experts = groups['experts'] if cached else 0
        # Three new 512-entry pointer/generation tables; reserve double-buffered
        # tables in admission, as 58g does. Actual census uses one generation.
        actual_tables = 3 * 512 * 16 if cached else 0
        bound_tables = 2 * actual_tables
        host_tables_and_routes = actual_tables + 10 * 12 if cached else 0
        actual_extra = device_extra - experts + actual_tables
        bound_extra = immutable_plus_kv - experts + bound_tables
        host_extra = experts + pinned + host_tables_and_routes + bound_extra
        bound = plan['device_owned_bound_bytes'] + bound_extra
        options[label] = dict(
            extra_device_payload_bytes=actual_extra,
            extra_direct_host_payload_bytes=experts + pinned + host_tables_and_routes,
            extra_host_admission_bytes=host_extra,
            proposed_device_payload_bytes=target['totals']['device'] + actual_extra,
            proposed_device_bound_bytes=bound,
            device_margin_after_1_5GB_reserve_bytes=32_000_000_000 - 1_500_000_000 - bound,
            timing_required_bytes=base_required + host_extra,
            timing_with_observed_shadow_bytes=base_required + host_extra + shadow,
            exactness_required_bytes=exact_required + host_extra,
            timing_margins_vs_observed_available_bytes={w: n - base_required - host_extra for w, n in available.items()},
            expert_pool_added_bytes=experts, cache_capacity_added_bytes=0,
            pointer_table_device_bytes=actual_tables,
            pointer_table_admission_bytes=bound_tables)
        option = options[label]
        option['fits_with_retained_allowances'] = (
            option['device_margin_after_1_5GB_reserve_bytes'] > 0 and
            bound <= plan['arena_limit_bytes'] and
            max(option['timing_margins_vs_observed_available_bytes'].values()) > 0)
    source_tensors = [line.split() for line in raw('draft_manifest').splitlines()]
    memory = dict(
        base_device_bytes=target['totals']['device'], base_host_pinned_bytes=target['totals']['host-pinned'],
        base_plan_device_bound_bytes=plan['device_owned_bound_bytes'],
        base_timing_required_bytes=base_required, base_exactness_required_bytes=exact_required,
        base_exact_host_categories=plan['exact_host_categories'], host_reserve_bytes=8 * GIB,
        historical_admission_available_bytes=available, measured_shadow_bytes=shadow,
        draft_weights_by_group=groups, draft_weight_rows=weights,
        draft_kv_bytes=kv, draft_workspace_bytes=workspace, draft_pinned_bytes=pinned,
        draft_head_additional_bytes=0, prefix_rows=91_392, prefix_shared_bytes=91_392 * 3380,
        embedding_weight_additional_bytes=0, embedding_output_bytes_already_in_workspace=5120,
        official_draft_source_bytes=sum(int(r[3]) for r in source_tensors),
        largest_source_tensor_bytes=max(int(r[3]) for r in source_tensors),
        target_mutable_row_bytes=mutable_bytes, private_state_reservations=transaction,
        transaction_allowance_remaining_bytes=plan['device_categories']['control_transaction_bound']-transaction_bytes,
        options=options,
        passed=any(v['fits_with_retained_allowances'] for v in options.values()),
        admission_policy='Use the most favorable retained KD/WS/WS128x available-memory snapshot; keep every original allowance and both reserves.',
        interpretation='Exact payload arithmetic for declared conservative layout; no new allocation/device-fit test. Existing workspace/control allowances retained, not double charged.')

    baseline = read('baseline')['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
    token_ms = 1000 / baseline
    model = read('model85')
    d = model['baseline']['components_ms']['D']
    acceptance = model['baseline']['median_acceptance']
    restore = statistics.median(r['restore_ms'] for r in read('restore68')['rows'])
    proxies = []
    for rank in (0, 1):
        rows = [json.loads(line) for line in raw(f'm2_rank{rank}').splitlines()]
        selected = [r for r in rows if r['row_kind'].startswith('consecutive')]
        require(len(selected) == 39 and all(r['byte_identity'] and r['differing_route_sites'] > 0 for r in selected),
                'representative consecutive M2 sample gate differs')
        proxies.append(dict(rank=rank, samples=len(selected), **{
            f'{half}_{metric}': statistics.median(r[half][metric] for r in selected)
            for half in ('H1', 'H2') for metric in ('device_sum_ms', 'wall_ms')}))
    h1 = sum(r['H1_device_sum_ms'] for r in proxies)
    h2 = sum(r['H2_device_sum_ms'] for r in proxies)
    wall_delta = sum(r['H2_wall_ms'] - r['H1_wall_ms'] for r in proxies)
    causal = sum(model['depth2']['op_duration_ms'][f'r{r}_op14_spec0']['mean'] for r in (0, 1))
    scenarios = {}
    for name, verify, rollback in (
        ('scale_device_ratio_no_rollback', token_ms * h2 / h1, 0),
        ('constant_onecard_overhead_device_no_rollback', token_ms + h2 - h1, 0),
        ('constant_onecard_overhead_wall_no_rollback', token_ms + wall_delta, 0),
        ('constant_onecard_overhead_device_with_restore68', token_ms + h2 - h1, (1-acceptance)*restore),
        ('constant_onecard_overhead_wall_with_restore68', token_ms + wall_delta, (1-acceptance)*restore),
        ('causal71c_command_no_onecard_penalty', causal, 0),
        ('serial_M1_no_rollback', 2 * token_ms, 0)):
        cycle = d + verify + rollback
        speed = 1000 * (1 + acceptance) / cycle
        scenarios[name] = dict(verify_ms=verify, rejection_restore_expectation_ms=rollback,
                              cycle_ms=cycle, predicted_tok_s=speed,
                              percent_vs_24=100*(speed/24-1), clears_28_8=speed >= 28.8)
    timing = dict(baseline_tok_s=baseline, baseline_equivalent_ms=token_ms,
        baseline_scope='WS128x shared-host exactness window, 128 output tokens; diagnostic timing only',
        measured_miss_mode='zero-copy', draft_ms=d, transferred_acceptance=acceptance,
        restore68_ms=restore, proxies=proxies, combined_M2_M1_ratio=h2/h1,
        required_tok_s=28.8, max_verify_ms=1000*(1+acceptance)/28.8-d,
        required_verify_ratio=(1000*(1+acceptance)/28.8-d)/token_ms,
        scenarios=scenarios, passed=scenarios['scale_device_ratio_no_rollback']['clears_28_8'],
        decision_policy='Primary estimate transfers the differing-route M2/M1 ratio; constant-overhead and causal-command scenarios test sensitivity.',
        formula='reward=1+a; hit cycle=D+V2; mean cycle=D+V2+(1-a)*R; no rank overlap',
        caveat='Cross-run diagnostic models, not a measured 58h rate. No extra draft feedback, cache miss, eviction, causal-copy or host overhead charged.')
    passed = memory['passed'] and timing['passed']
    return dict(schema='packet58h.feasibility.v1', device_executed=False, model_executed=False,
                decision='build-candidate' if passed else 'do-not-build',
                build_gate_passed=passed, memory=memory, timing=timing)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--verify-sources', action='store_true')
    args = parser.parse_args()
    require(not (args.capture and args.check), 'choose capture or check')
    resource.setrlimit(resource.RLIMIT_AS, (8 * GIB, 8 * GIB))
    require(os.getpriority(os.PRIO_PROCESS, 0) >= 19, 'use nice -n 19')
    require(set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'use helper cores')
    require(shutil.disk_usage(REPO).free >= 12 * GIB, 'root disk below 12 GiB; stop')
    if args.capture:
        capture()
    if args.verify_sources:
        manifest = json.loads((HERE / 'inputs.json').read_text())
        pins = dict(manifest['source_pins'])
        pins.update({v['source']: v['source_sha256'] for v in manifest['inputs'].values()})
        for path, expected in pins.items():
            require(sha((REPO / path).read_bytes()) == expected, 'original source changed: ' + path)
    result = analyze()
    path = HERE / 'feasibility.json'
    if args.check:
        require(result == json.loads(path.read_text()), 'analysis changed')
    else:
        dump(path, result)
    require(shutil.disk_usage(REPO).free >= 12 * GIB, 'root disk below 12 GiB; stop')
    print(json.dumps(dict(passed=True, decision=result['decision'],
                         peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
                         packet_bytes=sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file()))))


if __name__ == '__main__':
    main()
