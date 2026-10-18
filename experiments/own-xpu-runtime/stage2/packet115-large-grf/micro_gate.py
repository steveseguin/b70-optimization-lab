"""Fail-closed real-route micro gate. Diagnostic evidence, never model speed."""
import gzip
import hashlib
import json
import math
import statistics
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
CANDIDATES = ('e3-next', 'iq4-bytepair', 'v4-batch2-shared', 'e5-shared')
CONTROLS = ('production', 'production-large')
ROUTE_COUNT = 384
THRESHOLD = 0.85
QUALIFICATION = 'evidence/micro-qualification.json'

def require(ok, message):
    if not ok:
        raise ValueError(message)

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def read(path):
    return json.loads(Path(path).read_text())

def save(path, row):
    Path(path).write_text(json.dumps(row, indent=2, sort_keys=True)+'\n')

def verify_map(root, mapping):
    require(bool(mapping), 'empty identity map')
    for name, digest in mapping.items():
        if isinstance(digest, dict):
            digest = digest['sha256']
        require(sha(Path(root)/name) == digest, 'identity changed: '+name)

def shape(name):
    return (2560, 640) if name == 'iq4-bytepair' else (640, 2560)

def analyze(rows):
    require(rows and sum(r.get('kind') == 'summary' for r in rows) == 1,
            'one complete native summary required')
    end = rows[-1]
    require(end.get('kind') == 'summary' and all(end.get(k) is True for k in ('passed', 'drained', 'diagnostic_only')),
            'native run did not pass and drain')
    require(end.get('route_count') == ROUTE_COUNT and end.get('candidates') == list(CANDIDATES),
            'complete 384-route/four-candidate summary required')
    correct, samples = {}, {}
    for row in rows[:-1]:
        name, control, route = row.get('pair') if row.get('kind') == 'sample' else row.get('view'), row.get('control'), row.get('route')
        require(name in CANDIDATES and control in CONTROLS and type(route) is int and 0 <= route < ROUTE_COUNT,
                'unknown candidate/control/route')
        require((row.get('rows'), row.get('columns')) == shape(name) and row.get('count') == 10 and row.get('experts') == 512,
                'wrong full-bank expert shape')
        key = (route, name, control)
        if row.get('kind') == 'correctness':
            require(key not in correct and all(row.get(k) is True for k in ('all_bytes_exact', 'bf16_exact', 'status_exact')),
                    'duplicate correctness row or device bytes differ')
            correct[key] = row
        else:
            require(row.get('kind') == 'sample', 'unknown native row kind')
            rep, pos = row.get('repeat'), row.get('position')
            require(type(rep) is int and rep in (0, 1) and type(pos) is int and pos in (0, 1),
                    'wrong alternating order index')
            expected = name if pos ^ (rep & 1) else control
            require(row.get('view') == expected, 'nonalternating sample')
            require((row.get('wg'), row.get('sg'), row.get('scrub_bytes')) == (64, 32, 536870912)
                    and row.get('diagnostic_only') is True, 'wrong geometry or cache scrub')
            ns = row.get('event_ns')
            require(type(ns) in (int, float) and math.isfinite(ns) and ns > 0, 'invalid event timing')
            sample_key = (*key, rep, pos)
            require(sample_key not in samples, 'duplicate timing row')
            samples[sample_key] = row
    require(len(correct) == ROUTE_COUNT * len(CANDIDATES) * len(CONTROLS), 'missing correctness route/control')
    require(len(samples) == len(correct) * 4, 'missing timing route/order/control')
    result, qualified = {}, []
    for name in CANDIDATES:
        controls, passed = {}, True
        for control in CONTROLS:
            route_rows, ct, vt, order_ratios = [], [], [], [[], []]
            for route in range(ROUTE_COUNT):
                ratios = []
                for rep in (0, 1):
                    pair = [samples[(route, name, control, rep, pos)] for pos in (0, 1)]
                    times = {r['view']: r['event_ns'] for r in pair}
                    ratio = times[name] / times[control]
                    ratios.append(ratio)
                    order_ratios[rep].append(ratio)
                    ct.append(times[control]); vt.append(times[name])
                route_rows.append(dict(route=route, order_time_ratios=ratios, diagnostic_only=True))
            aggregate = statistics.median(order_ratios[0] + order_ratios[1])
            order = [statistics.median(values) for values in order_ratios]
            control_passed = aggregate <= THRESHOLD and max(order) <= THRESHOLD
            passed = passed and control_passed
            controls[control] = dict(qualified=control_passed, time_ratio=aggregate,
                                    order_time_ratios=order, worst_route_ratio=max(max(r['order_time_ratios']) for r in route_rows),
                                    production_event_ns=statistics.median(ct), candidate_event_ns=statistics.median(vt),
                                    ratio_of_event_medians_diagnostic=statistics.median(vt)/statistics.median(ct),
                                    routes=route_rows)
        result[name] = dict(qualified=passed, controls=controls)
        if passed:
            qualified.append(name)
    return dict(schema='packet115.micro-process-qualification.v1', passed=True, diagnostic_only=True,
                route_count=ROUTE_COUNT, candidates=result, qualified=qualified,
                threshold=dict(candidate_time_at_most_fraction=THRESHOLD, each_control=True,
                               both_orders=True, every_route=False, all_routes_measured=True,
                               aggregate='median of matched route candidate/control time ratios'))

def validate_processes(windows):
    require(len(windows) == 2, 'two fresh process receipts required')
    identities = []
    for repeat, row in enumerate(windows, 1):
        require(row.get('repeat') == repeat and all(row.get(k) is True for k in ('passed', 'device_executed', 'drained', 'lease_released')),
                'clean numbered device window required')
        require(type(row.get('pid')) is int and row['pid'] > 0 and type(row.get('process_start_ticks')) is int and row['process_start_ticks'] > 0
                and isinstance(row.get('boot_id'), str) and row['boot_id'], 'fresh process identity missing')
        require(type(row.get('started_utc_ns')) is int and type(row.get('finished_utc_ns')) is int
                and row['finished_utc_ns'] > row['started_utc_ns'], 'process wall interval missing')
        identities.append([row['boot_id'], row['pid'], row['process_start_ticks']])
    require(identities[0] != identities[1], 'same native process reused')
    require(windows[0]['finished_utc_ns'] <= windows[1]['started_utc_ns'], 'fresh process windows overlap or are reversed')
    return identities

def prerequisites(packet=P):
    packet = Path(packet)
    build = packet/'evidence/microbench-build.json'
    images = packet/'evidence/images.json'
    cpu = packet/'evidence/cpu-byte-identity.json'
    for path in (build, images, cpu):
        require(path.is_file(), 'micro prerequisite pending: '+str(path))
    b, im, c = read(build), read(images), read(cpu)
    for row, label in ((b, 'micro build'), (c, 'CPU identity')):
        require(row.get('passed') is True and row.get('device_executed') is False, label+' incomplete')
        verify_map(ROOT, row['sources'])
        if row.get('generated_sources'):
            verify_map(ROOT, row['generated_sources'])
    require(set(c.get('views', {})) == {'production', *CANDIDATES}, 'complete CPU views required')
    for name, view in c['views'].items():
        require(view.get('passed') is True and len(view.get('runs', [])) == 4, 'CPU view incomplete: '+name)
        require({(r.get('compiler'), r.get('repeat')) for r in view['runs']} == {('GNU', 1), ('GNU', 2), ('Intel', 1), ('Intel', 2)}, 'CPU fresh compiler/repeat coverage missing')
        for run in view['runs']:
            require(run.get('passed') is True and run.get('device_executed') is False and run['expected_sha256'] == run['candidate_sha256'], 'CPU bytes differ')
            for key in ('raw_evidence', 'cases_path', 'log_path'):
                digest_key = {'raw_evidence': 'raw_evidence_sha256', 'cases_path': 'cases_sha256', 'log_path': 'log_sha256'}[key]
                require(sha(ROOT/run[key]) == run[digest_key], 'CPU evidence changed')
            require(hashlib.sha256(gzip.decompress((ROOT/run['raw_evidence']).read_bytes())).hexdigest() == run['candidate_sha256'], 'CPU retained output bytes changed')
    for compiler in c['compilers']:
        require(sha(ROOT/compiler['binary']) == compiler['binary_sha256'], 'CPU binary changed')
    verify_map(packet, b['artifacts'])
    require(b['artifacts'].get('build/microbench') == sha(packet/'build/microbench'), 'unbound micro binary')
    require(im.get('passed') is True and im.get('device_executed') is False, 'zero-spill image gate incomplete')
    require({r.get('mode') for r in im.get('images', [])} == {'normal', 'large'}, 'both allocation-mode images required')
    for row in im['images']:
        require(row.get('returncode') == 0, 'image compilation failed')
        verify_map(ROOT, row['sources'])
        verify_map(packet, row['artifact'])
        require(sha(packet/row['zeinfo']['path']) == row['zeinfo']['sha256'], 'image scratch allocation metadata changed')
        kernels = [k for k in row['kernels'] if 'Intel_Symbol_Table_Void_Program' not in k.get('name', '')]
        require(kernels and all(k.get('spill_free') is True for k in kernels), 'spilled expert kernel')
        if row['mode'] == 'large':
            require(all(k.get('grf') == 256 for k in kernels), 'LARGE GRF mode not established')
        for kernel in row['kernels']:
            require(sha(packet/kernel['assembly']) == kernel['sha256'], 'register report assembly changed')
    from route_inputs import read_inputs, MANIFEST, ROUTES
    route = read_inputs()
    require(route['micro_route_vectors'] == ROUTE_COUNT and sha(ROUTES) == route['route_bytes_sha256'], 'route capture changed')
    paths = (build, images, cpu, Path(MANIFEST), Path(ROUTES), packet/'micro_gate.py', packet/'run_micro.py', packet/'route_inputs.py')
    return {str(path.relative_to(packet)): sha(path) for path in paths}

def one_process(packet, repeat, bindings):
    packet = Path(packet); directory = packet/('evidence/micro-B-'+str(repeat))
    receipt, samples = directory/'window.json', directory/'samples.jsonl'
    require(receipt.is_file() and samples.is_file(), 'micro process '+str(repeat)+' pending')
    window = read(receipt)
    require(window.get('repeat') == repeat and all(window.get(k) is True for k in ('passed', 'device_executed', 'drained', 'lease_released')),
            'clean numbered micro window required')
    require(window.get('binary_sha256') == sha(packet/'build/microbench') and window.get('build_receipt_sha256') == bindings['evidence/microbench-build.json'],
            'micro build identity changed')
    require(window.get('prerequisite_bindings') == bindings, 'run prerequisite hashes differ')
    require(window.get('samples_sha256') == sha(samples), 'native sample bytes changed')
    result = analyze([json.loads(line) for line in samples.read_text().splitlines() if line.strip()])
    result['bindings'] = {str(path.relative_to(packet)): sha(path) for path in (receipt, samples)}
    result['repeat'] = repeat
    return result, window

def measured(packet=P):
    packet = Path(packet); bindings = prerequisites(packet)
    pairs = [one_process(packet, repeat, bindings) for repeat in (1, 2)]
    identities = validate_processes([window for _, window in pairs])
    results = [result for result, _ in pairs]
    qualified = [name for name in CANDIDATES if all(name in result['qualified'] for result in results)]
    for result in results:
        bindings.update(result['bindings'])
    return dict(schema='packet115.micro-qualification.v1', passed=True, diagnostic_only=True,
                qualified=qualified, processes=results, process_identities=identities, bindings=bindings)

def evaluate(packet=P, repeat=None):
    packet = Path(packet)
    if repeat is not None:
        bindings = prerequisites(packet)
        result, _ = one_process(packet, repeat, bindings)
        save(packet/('evidence/micro-B-'+str(repeat))/'qualification.json', result)
        if not all((packet/('evidence/micro-B-'+str(n))/'window.json').is_file() for n in (1, 2)):
            return dict(passed=False, pending=True, qualified=[], reason='second fresh process pending')
    result = measured(packet)
    save(packet/QUALIFICATION, result)
    return result

def require_qualified(packet=P):
    packet = Path(packet); path = packet/QUALIFICATION
    require(path.is_file(), 'two-process micro qualification pending')
    saved, fresh = read(path), measured(packet)
    require(saved == fresh, 'micro qualification stale or altered')
    require(bool(fresh['qualified']), 'no candidate passed both orders/controls/processes; v5 refused')
    return tuple(fresh['qualified'])
