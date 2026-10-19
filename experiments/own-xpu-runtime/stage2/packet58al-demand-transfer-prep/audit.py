"""Small CPU-only source/evidence audit. No sibling imports or native commands.

Reads whitelisted source/JSON/JSONL and directory sizes, never model payloads.
Writes only this packet's evidence. Not a runtime gate or replacement analyzer.
"""
import collections
import datetime
import hashlib
import json
import math
from pathlib import Path
import resource
import statistics

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
STAGE = P.parent
AH = STAGE / 'packet58ah-onecard-record'
AG = STAGE / 'packet58ag-onecard-ports'
AI = STAGE / 'packet58ai-miss-census'
resource.setrlimit(resource.RLIMIT_AS, (2 * 1024**3, 2 * 1024**3))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def rel(path):
    return str(path.relative_to(ROOT))


def digest(path):
    require(path.suffix in {'.py', '.cpp', '.hpp', '.json', '.jsonl', '.tsv', '.md'},
            'only source/evidence hashing allowed')
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    require(path.stat().st_size <= 32 * 1024**2, 'oversize JSON: ' + rel(path))
    return json.loads(path.read_text())


def rows(path):
    with path.open() as stream:
        for line in stream:
            require(len(line) <= 1024**2, 'oversize row')
            if line.strip():
                yield json.loads(line)


def write(name, value):
    (P / 'evidence').mkdir(exist_ok=True)
    dest = P / 'evidence' / name
    temp = dest.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')
    temp.replace(dest)


def source_map():
    receipt = AH / 'lineage/58ag-build-receipt.json'
    pinned = read(receipt)['sources']
    sites = {
        AH / 'lineage/58ag-snapshot/sources/main.cpp':
            [[842, 918], [1195, 1214], [1358, 1365], [1417, 1450],
             [1486, 1506], [1809, 1857]],
        AH / 'lineage/58ag-snapshot/native/engine_bracket.hpp': [[1, 52]],
        AH / 'lineage/58ag-snapshot/native_source.py': [[1, 35]],
        AH / 'memory_plan.py': [[1, 35]],
        AG / 'build/native/main.cpp':
            [[589, 663], [852, 905], [919, 1025], [1307, 1321],
             [1524, 1550], [1592, 1610], [1963, 2010]],
        AG / 'build/native/single_device.cpp':
            [[26, 45], [77, 97], [110, 131], [167, 201]],
        AG / 'build/native/owner.cpp': [[168, 212], [317, 367]],
        AG / 'native/cache_protocol.hpp': [[7, 42]],
        AG / 'native/cache_table.hpp': [],
        AG / 'build/native/p58ag_expert.hpp': [[67, 118]],
        AG / 'build/native/p58ag_submit.cpp': [[6, 38]],
        AG / 'build/native/p109_fusion.hpp': [[32, 42], [74, 82]],
    }
    suffixes = {
        '/packet58j-onecard-port/p58_pointer.hpp': [[6, 15]],
        '/packet58j-onecard-port/p100_down.hpp': [[12, 29], [31, 71], [91, 118]],
        '/packet9-kopt4/reference.hpp': [[16, 24]],
        '/packet58j-onecard-port/p49b_gemv.hpp': [[11, 25]],
    }
    for suffix, spans in suffixes.items():
        found = [ROOT / k for k in pinned if k.endswith(suffix)]
        require(len(found) == 1, 'unambiguous pinned source: ' + suffix)
        sites[found[0]] = spans
    bound = read(AH / 'parent-binding.json')['sources']
    own_sources = read(AH / 'build-receipt.json')['sources']
    result = []
    for path, spans in sites.items():
        actual = digest(path)
        expected = pinned.get(rel(path), bound.get(rel(path), own_sources.get(rel(path))))
        require(expected == actual, 'source changed: ' + rel(path))
        count = len(path.read_text().splitlines())
        require(all(1 <= lo <= hi <= count for lo, hi in spans),
                'source line range outside file: ' + rel(path))
        result.append(dict(path=rel(path), sha256=actual, physical_line_ranges=spans,
                           lines=count, matches_parent_pin=True))
    return dict(schema='packet58al.source-map.v1', source_receipt=rel(receipt),
                source_receipt_sha256=digest(receipt), files=result)


def parent_audit():
    result_path = AH / 'submission/prepared-b/result.json'
    result = read(result_path)
    window = AH / 'evidence/card0-58ah-b/WS128'
    wr = read(window / 'window.json')
    native = read(window / 'run/receipt.json')
    require(wr['passed'] and wr['device_executed'] and not wr['child_still_running']
            and not wr['stop_reasons'], 'parent window incomplete')
    rates, class_rates, cold, inventory = [], collections.defaultdict(list), [], []
    for published in result['rows']:
        # The result packet's naming is audited below, not guessed from filenames.
        prompt = published['prompt_id']
        folder = window / 'run/run' / prompt
        path = folder / 'result.json'
        d = read(path)
        require(d['passed'] and d['arithmetic'] == 'iq3-p49-split32-v1'
                and d['cached_tokens'] == 0 and len(d['tokens']) == 128,
                'parent request identity')
        times = [r['completed_monotonic'] for r in d['timing_rows']]
        require(len(times) == 128 and all(b > a for a, b in zip(times, times[1:])),
                'parent timestamps')
        require(times == published['token_timestamps'], 'result timestamp binding')
        rate = 99 / (times[99] - times[0])
        rates.append(rate)
        cls = published['prompt_class']
        class_rates[cls].append(rate)
        generated = list(rows(folder / 'timings.jsonl'))
        prefill = list(rows(folder / 'prefill-timings.jsonl'))
        require(len(generated) == 128 and len(prefill) == d['prompt_tokens'] - 1,
                'cold/warm token coverage')
        require([r['generated_index'] for r in generated] == list(range(1, 129)),
                'generated sequence')
        require([r['token_id'] for r in generated] == d['tokens'], 'output binding')
        require(math.isclose(generated[0]['wall_ms'], d['first_generated_token_ms'],
                             rel_tol=.02, abs_tol=.001), 'first-token duration consistency')
        for name in ['result.json', 'timings.jsonl', 'prefill-timings.jsonl']:
            f = folder / name
            inventory.append(dict(path=rel(f), sha256=digest(f), bytes=f.stat().st_size))
        cold.append(dict(prompt_id=prompt, request_start_monotonic=d['request_start_monotonic'],
                         prefill_rows=len(prefill), generated_rows=len(generated),
                         first_prefill_row=prefill[0], first_generated_row=generated[0],
                         prefill_total_ms=d['prefill_ms'],
                         first_generated_token_ms=d['first_generated_token_ms'],
                         maximum_prefill_token_ms=max(r['wall_ms'] for r in prefill),
                         conventional_99_interval_tok_s=rate))
    primary = statistics.median(statistics.median(v) for v in class_rates.values())
    require(math.isclose(primary, result['primary_metric']['value_tok_s'], rel_tol=1e-12),
            'parent primary reconstruction')
    cold.sort(key=lambda r: r['request_start_monotonic'])
    sizes = []
    for name in ['K1a', 'K1b', 'KD', 'WS128']:
        folder = window.parent / name
        files = [f for f in folder.rglob('*') if f.is_file() and not f.is_symlink()]
        sizes.append(dict(path=rel(folder), files=len(files),
                          logical_bytes=sum(f.stat().st_size for f in files),
                          method='stat sizes only; no model or binary reads'))
    # Enclosing phase is a conservative wait-sizing input, not a per-op measurement.
    phase_ms = max(r['prefill_total_ms'] for r in cold)
    admission_path = AH / 'admission.json'
    admission = read(admission_path)['admission']
    per_expert = 2 * 640 * 820 + 2560 * 360
    staged = 2 * 32 * per_expert
    host_increment = staged + 1024**2 + 2 * 1024**2
    require(staged == 126_156_800, 'stage arithmetic')
    require(admission['host_bound_bytes'] + host_increment == 90_529_619_968,
            'proposed host bound')
    require(admission['host_required_available_bytes'] + host_increment == 99_119_554_560,
            'proposed host available floor')
    accounting = dict(source=rel(admission_path), sha256=digest(admission_path),
        planned_not_measured=True, admitted_for_device=False,
        per_expert_bytes=per_expert, stage_bytes=staged,
        device_map_cap_bytes=1024**2, host_metadata_cap_bytes=2 * 1024**2,
        inherited_transfer_allowance_bytes=admission['device_categories']['transfer_bound'],
        transfer_allowance_left_for_inherited_allocations_bytes=
            admission['device_categories']['transfer_bound'] - staged - 1024**2,
        host_added_backing_and_metadata_bytes=host_increment,
        host_bound_bytes=admission['host_bound_bytes'] + host_increment,
        host_required_available_bytes=admission['host_required_available_bytes'] + host_increment,
        unchanged_host_reserve_bytes=admission['host_reserve_bytes'],
        unchanged_device_owned_bound_bytes=admission['device_owned_bound_bytes'],
        unassigned_device_capacity_bytes=admission['physical_capacity_floor_bytes']
            - admission['device_owned_bound_bytes'] - admission['driver_allowance_bytes']
            - admission['device_reserve_bytes'],
        remaining_gate='full simultaneous allocation census, live admission, owner lifetime and bounded metadata proof')
    return dict(schema='packet58al.parent-audit.v1', passed=True,
                scope='read-only real parent timings/source identity; not new quality or demand validation',
                result=rel(result_path), result_sha256=digest(result_path),
                parent_window=rel(window / 'window.json'),
                parent_window_sha256=digest(window / 'window.json'),
                native_receipt=rel(window / 'run/receipt.json'),
                native_receipt_sha256=digest(window / 'run/receipt.json'),
                native_argv=native['command'],
                primary_reconstructed_tok_s=primary, requests=len(cold),
                first_request=cold[0], request_cold_rows=cold,
                duration_check=dict(rel_tol=.02, abs_tol_ms=.001,
                                    data_wall_clock_limit_seconds=None),
                proposed_initial_wait_seconds=max(300, math.ceil(4 * phase_ms / 1000)),
                wait_basis='4x largest enclosing measured parent prefill, minimum300s; not a per-op measurement; refresh with completed census',
                measured_directory_sizes=sizes, proposed_stage_accounting=accounting,
                file_pins=inventory)


def poll():
    reports = []
    for path in sorted((AI / 'evidence').rglob('census-analysis.json')):
        before = digest(path)
        try:
            data = read(path)
        except (ValueError, json.JSONDecodeError) as error:
            reports.append(dict(path=rel(path), status='incomplete-or-oversize', error=str(error)))
            continue
        after = digest(path)
        keep = ['passed', 'status', 'device_executed', 'decision',
                'upper_bound_ms_per_token', 'split_miss_service_ceiling_ms_per_token',
                'means', 'counts', 'cache_demand_identical', 'overhead',
                'measurement_stability_gate', 'record_tok_s', 'streams',
                'actual_concurrent_overlap_ms']
        reports.append(dict(path=rel(path), sha256=after, stable_read=before == after,
                            fields={k: data[k] for k in keep if k in data},
                            qualification='observed report; owning analyzer/native closure must still be replayed before build release'))
    ready = read(AI / 'READY-FOR-DEVICE.json')
    attempts = []
    for path in sorted((STAGE.parent / 'ops/lane-queue').glob('packet58ai*.exit.json')):
        attempts.append(dict(path=rel(path), sha256=digest(path), fields=read(path)))
    note = ROOT / 'notes/2026-10-19-own-runtime-packet58ai.md'
    identity = AI / 'evidence/p58aic-identity.json'
    return dict(schema='packet58al.census-observation.v1',
                observed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                census_readiness_sha256=digest(AI / 'READY-FOR-DEVICE.json'),
                census_declared_record_tok_s=ready.get('record_tok_s'),
                census_preparation_probe=ready.get('preparation_path_probe'),
                census_preparation_scope=ready.get('readiness_scope'),
                census_attempt_exits=attempts,
                coordinator_identity_repair=dict(path=rel(identity), sha256=digest(identity),
                    evidence=read(identity)) if identity.exists() else None,
                census_work_note=dict(path=rel(note), sha256=digest(note)),
                reports=reports,
                status='reports-observed-review-required' if reports else 'pending-completed-census',
                upper_bound_ms_per_token=None if not reports else 'see individual report; no unqualified aggregate',
                build_released=False, device_readiness=False,
                action='Apply DECISION.md only to a complete, exact, stable, hash-bound census; no launch from this prep')


if __name__ == '__main__':
    import os
    stat = os.statvfs(P)
    require(stat.f_bavail * stat.f_frsize >= 27_000_000_000, 'CPU preparation disk floor')
    write('source-map.json', source_map())
    audit = parent_audit()
    write('parent-audit.json', audit)
    write('poll.json', poll())
    print(json.dumps(dict(passed=True, source_map=True, real_parent_requests=audit['requests'],
                          primary_reconstructed_tok_s=audit['primary_reconstructed_tok_s'],
                          first_prefill_ms=audit['first_request']['first_prefill_row']['wall_ms'],
                          peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                          device_executed=False, model_reads=False)))
