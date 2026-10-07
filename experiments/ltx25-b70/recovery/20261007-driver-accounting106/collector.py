#!/usr/bin/env python3
"""Bounded read-only DRM accounting; raw counters, never utilization or device work."""
import argparse
import hashlib
import itertools
import json
import os
import re
from pathlib import Path
import stat
import time

MAX_FDS = 4096
MAX_TASKS = 512
MAX_RENDER = 32
MAX_READ = 16384
MAX_OUTPUT = 131072
MAX_SAMPLES = 64
DURATION = 120
INTERVAL = 2
TERMINAL_RESERVE = 512


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path, limit=MAX_READ):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        require(stat.S_ISREG(os.fstat(fd).st_mode), 'Nonregular evidence')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            value = stream.read(limit + 1)
        require(len(value) <= limit, 'Read cap exceeded')
        return value
    finally:
        os.close(fd)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def strict(raw):
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, 'Duplicate JSON key')
            out[k] = v
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: require(False, 'Nonfinite JSON'))


def bounded_entries(path, cap):
    with os.scandir(path) as entries:
        values = list(itertools.islice(entries, cap + 1))
    require(len(values) <= cap, 'Directory coverage cap exceeded')
    return sorted(values, key=lambda e: e.name)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()


def safe_path(value):
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts and
            not any(p.is_symlink() for p in (path, *path.parents)), 'Unsafe evidence path')
    return path


def checked_source(binding):
    require(set(binding) == {'path', 'sha256'} and
            re.fullmatch('[0-9a-f]{64}', binding['sha256']), 'Invalid source binding')
    raw = read(safe_path(binding['path']), 2**21)
    require(digest(raw) == binding['sha256'], 'Bound source changed')
    return raw


def load_contract(path, expected):
    raw = read(safe_path(path), 65536)
    require(digest(raw) == expected, 'Contract digest differs')
    c = strict(raw)
    require(c['schema'] == 'ltx.raw-drm-accounting.v1', 'Contract schema differs')
    require(type(c['pid']) is int and c['pid'] > 0, 'Invalid PID')
    require(type(c['start_ticks']) is str and c['start_ticks'].isdigit() and
            isinstance(c['boot_id'], str) and c['boot_id'], 'Invalid process identity')
    require(isinstance(c['render_nodes'], dict) and 1 <= len(c['render_nodes']) <= 4, 'Render admission differs')
    require(all(re.fullmatch(r'/dev/dri/renderD[0-9]+', k) and
                re.fullmatch(r'[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]', v)
                for k, v in c['render_nodes'].items()), 'Invalid render/PCI mapping')
    require(len(set(c['render_nodes'].values())) == len(c['render_nodes']), 'Duplicate PCI admission')
    require(isinstance(c['fault_paths'], list) and 1 <= len(c['fault_paths']) <= 8, 'Fault paths required')
    require(set(c['bindings']) == {'plan', 'server_identity', 'mapping_evidence', 'runtime_manifest'},
            'Source bindings required')
    check_bindings(c)
    return c


def check_bindings(c):
    require(c['collector_sha256'] == digest(read(Path(__file__).resolve(), 65536)), 'Collector source differs')
    docs = {name: strict(checked_source(binding)) for name, binding in c['bindings'].items()}
    identity, envelope = docs['server_identity'], docs['plan']
    require(identity['pid'] == c['pid'] and str(identity['proc_start_ticks']) == c['start_ticks'] and
            identity['boot_id'] == c['boot_id'], 'Server identity differs')
    packet = safe_path(identity['source_packet_path'])
    require(Path(c['bindings']['runtime_manifest']['path']) == packet / 'manifest.json' and
            Path(c['bindings']['plan']['path']) == packet / 'resolution/candidate-plan.json', 'Server packet paths differ')
    require(identity['source_packet_manifest_sha256'] == c['runtime_manifest_sha256'] ==
            c['bindings']['runtime_manifest']['sha256'], 'Runtime manifest identity differs')
    require(set(envelope) == {'plan', 'plan_sha256'} and
            envelope['plan_sha256'] == c['plan_sha256'] == digest(canonical(envelope['plan'])) ==
            docs['runtime_manifest']['resolution101']['plan_sha256'] and
            envelope['plan']['qualification_id'] == c['qualification_id'], 'Server plan identity differs')
    require(docs['runtime_manifest']['files']['resolution/candidate-plan.json'] ==
            c['bindings']['plan']['sha256'], 'Manifest plan source differs')
    mapping = docs['mapping_evidence']
    require(mapping['schema'] == 'ltx.reviewed-render-xpu-map.v1' and
            mapping['review_method'] == 'reviewed-existing-evidence' and
            mapping['server_identity_sha256'] == c['bindings']['server_identity']['sha256'] and
            mapping['runtime_manifest_sha256'] == c['runtime_manifest_sha256'] and
            mapping['plan_sha256'] == c['plan_sha256'] and
            mapping['render_nodes'] == c['render_nodes'] and
            mapping['ordered_xpu_mapping'] == c['ordered_xpu_mapping'], 'Mapping evidence differs')
    order = mapping['ordered_xpu_mapping']
    require(isinstance(order, list) and len(order) == len(c['render_nodes']) == len(identity['devices']),
            'Incomplete ordered XPU mapping')
    for ordinal, (row, device) in enumerate(zip(order, identity['devices'])):
        require(set(row) == {'ordinal', 'render_node', 'pci', 'properties_sha256'} and
                type(row['ordinal']) is int and row['ordinal'] == device['ordinal'] == ordinal and
                c['render_nodes'].get(row['render_node']) == row['pci'] and
                row['properties_sha256'] == digest(device['properties'].encode()), 'Ordered XPU mapping differs')
    require({r['render_node'] for r in order} == set(c['render_nodes']), 'Repeated render in XPU mapping')
    sources = mapping['evidence_sources']
    require(isinstance(sources, list) and 1 <= len(sources) <= 8, 'Mapping evidence sources required')
    require(len({s['path'] for s in sources}) == len(sources), 'Duplicate mapping evidence source')
    for source in sources:
        checked_source(source)
    run = Path(c['bindings']['server_identity']['path']).parent
    required_faults = {str(run / 'FAULT.json'), str(run / 'resolution-halt.json'), str(run.parent / 'FAULT.json')}
    require(required_faults <= set(c['fault_paths']), 'Missing server fault paths')
    for path in c['fault_paths']:
        require(not os.path.lexists(safe_path(path)), 'Fault marker present; stop observation')


def process_identity(c, proc):
    base = proc / str(c['pid'])
    fields = read(base / 'stat').decode().rsplit(')', 1)[1].split()
    require(fields[0] not in ('Z', 'X', 'x'), 'Process is zombie or exited')
    boot = read(proc / 'sys/kernel/random/boot_id').decode().strip()
    require(fields[19] == c['start_ticks'] and boot == c['boot_id'], 'Process identity changed')


def parse_fdinfo(raw):
    fields = {}
    for line in raw.decode().splitlines():
        if ':' not in line:
            continue
        k, v = line.split(':', 1)
        if k.startswith('drm-'):
            require(k not in fields, 'Duplicate DRM field')
            fields[k] = v.strip()
    require(fields.get('drm-driver') == 'xe', 'Unexpected DRM driver')
    require(fields.get('drm-client-id', '').isdigit(), 'Missing client identity')
    result = {'pci': fields.get('drm-pdev'), 'client': fields['drm-client-id'], 'engines': {}}
    issues = []
    for engine in ('ccs', 'bcs'):
        values = {}
        for label, prefix in [('busy', 'drm-cycles-'), ('total', 'drm-total-cycles-'), ('capacity', 'drm-engine-capacity-')]:
            value = fields.get(prefix + engine)
            if value is None:
                if label == 'capacity':
                    values[label] = 1  # Documented generic DRM default, not a measured value.
                    values['capacity_defaulted'] = True
                else:
                    values[label] = None
                    issues.append('missing-' + engine + '-' + label)
            else:
                require(value.isdigit(), 'Malformed engine counter')
                values[label] = int(value)
                if label == 'capacity':
                    require(values[label] > 0, 'Invalid engine capacity')
                    values['capacity_defaulted'] = False
        result['engines'][engine] = values
    return result, issues


class Collector:
    def __init__(self, contract, proc=Path('/proc')):
        self.c, self.proc = contract, Path(proc)
        self.previous = None
        self.watermarks = {}

    def snapshot(self):
        c, proc = self.c, self.proc
        check_bindings(c)
        process_identity(c, proc)
        start = time.monotonic_ns()
        unix_start = time.time_ns()
        base = proc / str(c['pid'])
        issues, clients, nodes, descriptors = [], {}, set(), {}
        tasks = bounded_entries(base / 'task', MAX_TASKS)
        children = set()
        for task in tasks:
            children.update(read(Path(task.path) / 'children').decode().split())
        if children:
            issues.append('uncovered-child-processes')
        fds = bounded_entries(base / 'fd', MAX_FDS)
        render_count = 0
        for fd in fds:
            try:
                target = os.readlink(fd.path)
            except FileNotFoundError:
                issues.append('descriptor-vanished')
                continue
            descriptors[fd.name] = {'target': target}
            if not target.startswith('/dev/dri/renderD'):
                continue
            render_count += 1
            require(render_count <= MAX_RENDER, 'Render descriptor cap exceeded')
            require(target in c['render_nodes'], 'Unadmitted render node')
            row, errors = parse_fdinfo(read(base / 'fdinfo' / fd.name))
            require(row['pci'] == c['render_nodes'][target], 'Render/PCI admission mismatch')
            nodes.add(target)
            key = row['pci'] + '/' + row['client']
            descriptors[fd.name]['client_key'] = key
            issues.extend(errors)
            if key not in clients:
                row['selected_fd'] = fd.name
                row['duplicate_observations'] = []
                clients[key] = row
            else:
                selected = clients[key]
                for engine, values in row['engines'].items():
                    previous = selected['engines'][engine]
                    if (values['capacity'], values['capacity_defaulted']) != (previous['capacity'], previous['capacity_defaulted']):
                        issues.append('duplicate-capacity-conflict')
                    if any(values[k] is not None and previous[k] is not None and values[k] < previous[k]
                           for k in ('busy', 'total')):
                        issues.append('duplicate-counter-regression')
                selected['duplicate_observations'].append({'fd': fd.name, 'engines': row['engines']})
        if nodes != set(c['render_nodes']):
            issues.append('missing-admitted-render-node')
        if self.previous is not None and set(clients) != set(self.previous):
            issues.append('client-set-changed')
        for key, row in clients.items():
            for eng, values in row['engines'].items():
                old = (self.previous or {}).get(key, {}).get('engines', {}).get(eng)
                if old and (values['capacity'], values['capacity_defaulted']) != (old['capacity'], old['capacity_defaulted']):
                    issues.append('capacity-changed')
                if old and values['total'] is not None and old['total'] is not None and values['total'] <= old['total']:
                    issues.append('nonincreasing-total')
                for counter in ('busy', 'total'):
                    value = values[counter]
                    observed = ([value] if value is not None else []) + [
                        d['engines'][eng][counter] for d in row['duplicate_observations']
                        if d['engines'][eng][counter] is not None]
                    if not observed:
                        continue
                    watermark_key = key + '/' + eng + '/' + counter
                    high = self.watermarks.get(watermark_key, observed[0])
                    if value is not None and value < high:
                        issues.append(counter + '-below-watermark')
                    self.watermarks[watermark_key] = max(high, *observed)
                    values[counter + '_watermark'] = self.watermarks[watermark_key]
        end_tasks = bounded_entries(base / 'task', MAX_TASKS)
        if {e.name for e in end_tasks} != {e.name for e in tasks}:
            issues.append('task-set-changed')
        end_children = set()
        for task in end_tasks:
            end_children.update(read(Path(task.path) / 'children').decode().split())
        if end_children != children:
            issues.append('child-set-changed')
        children |= end_children
        if children:
            issues.append('uncovered-child-processes')
        end_fds = bounded_entries(base / 'fd', MAX_FDS)
        end_descriptors = {}
        render_end_count = 0
        # Re-enumerate ALL descriptors: new render handles cannot hide in FD churn.
        for fd in end_fds:
            try:
                target = os.readlink(fd.path)
                end_descriptors[fd.name] = {'target': target}
                if not target.startswith('/dev/dri/renderD'):
                    continue
                render_end_count += 1
                require(render_end_count <= MAX_RENDER, 'Render descriptor cap exceeded')
                require(target in c['render_nodes'], 'Unadmitted render node')
                after, errors = parse_fdinfo(read(base / 'fdinfo' / fd.name))
                require(after['pci'] == c['render_nodes'][target], 'Render/PCI admission mismatch')
                issues.extend(errors)
                key = after['pci'] + '/' + after['client']
                end_descriptors[fd.name]['client_key'] = key
                if key in clients and any((v['capacity'], v['capacity_defaulted']) !=
                         (clients[key]['engines'][eng]['capacity'], clients[key]['engines'][eng]['capacity_defaulted'])
                         for eng, v in after['engines'].items()):
                    issues.append('capacity-changed-during-scan')
            except FileNotFoundError:
                issues.append('descriptor-vanished')
        render_before = {fd: d for fd, d in descriptors.items() if 'client_key' in d}
        render_after = {fd: d for fd, d in end_descriptors.items() if 'client_key' in d}
        if set(render_before) != set(render_after):
            issues.append('render-descriptor-set-changed')
        for fd in render_before.keys() & render_after.keys():
            if render_before[fd]['target'] != render_after[fd]['target']:
                issues.append('descriptor-target-changed')
            if render_before[fd]['client_key'] != render_after[fd]['client_key']:
                issues.append('descriptor-client-changed')
        nonrender_before = {fd: d for fd, d in descriptors.items() if 'client_key' not in d}
        nonrender_after = {fd: d for fd, d in end_descriptors.items() if 'client_key' not in d}
        nonrender_churn = {'added': len(nonrender_after.keys() - nonrender_before.keys()),
                          'removed': len(nonrender_before.keys() - nonrender_after.keys()),
                          'retargeted': sum(nonrender_before[fd] != nonrender_after[fd]
                                            for fd in nonrender_before.keys() & nonrender_after.keys())}
        process_identity(c, proc)
        check_bindings(c)
        result = dict(unix_start_ns=unix_start, monotonic_start_ns=start, monotonic_end_ns=time.monotonic_ns(),
                      complete=not issues, issues=sorted(set(issues)), fd_count=len(fds),
                      task_count=len(tasks), child_pids=sorted(children), render_fd_count=render_count,
                      clients=clients, render_descriptors=render_before,
                      render_descriptors_after=render_after, nonrender_fd_churn=nonrender_churn)
        self.previous = clients
        return result


def fsync_parent(path):
    fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def run(c, output, contract_sha):
    collector = Collector(c)
    start = time.monotonic()
    used, recorded, missed = 0, 0, 0
    output = safe_path(output)
    status, reason, last_start = 'sample-cap', None, None
    output_failed = False
    with open(output, 'xb', buffering=0) as stream:
        def emit(value, terminal=False):
            nonlocal used, output_failed
            raw = json.dumps(value, separators=(',', ':'), allow_nan=False).encode() + b'\n'
            if used + len(raw) + (0 if terminal else TERMINAL_RESERVE) > MAX_OUTPUT:
                return False
            view = memoryview(raw)
            try:
                while view:
                    written = stream.write(view)
                    require(type(written) is int and 0 < written <= len(view), 'Incomplete output write')
                    used += written
                    view = view[written:]
            except BaseException:
                output_failed = True
                raise
            return True

        def finish():
            value = {'terminal': status, 'samples_recorded': recorded, 'missed_slots': missed}
            if reason is not None:
                value['reason'] = reason
            require(emit(value, terminal=True), 'Terminal output reserve exhausted')

        try:
            require(emit({'schema': 'ltx.raw-drm-snapshots.v1', 'contract_sha256': contract_sha,
                  'collector_sha256': c['collector_sha256'], 'bindings': c['bindings'],
                  'ordered_xpu_mapping': c['ordered_xpu_mapping'],
                  'pid': c['pid'], 'start_ticks': c['start_ticks'], 'boot_id': c['boot_id'],
                  'limits': {'seconds': DURATION, 'samples': MAX_SAMPLES, 'bytes': MAX_OUTPUT, 'interval': INTERVAL}}),
                    'Header exceeds output allowance')
            os.fsync(stream.fileno())
            fsync_parent(output)
            for i in range(MAX_SAMPLES):
                target = max(start + i * INTERVAL, last_start + INTERVAL if last_start is not None else start)
                if target >= start + DURATION:
                    status = 'duration-cap'
                    break
                if i and time.monotonic() > target + INTERVAL:
                    if not emit({'incomplete': 'missed-cadence', 'scheduled_sample': i}):
                        status = 'output-cap'
                        break
                    missed += 1
                    continue
                time.sleep(max(0, target - time.monotonic()))
                last_start = time.monotonic()
                if last_start >= start + DURATION:
                    status = 'duration-cap'
                    break
                try:
                    row = collector.snapshot()
                except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
                    status = 'observation-stopped'
                    reason = str(error).encode('ascii', 'replace').decode()[:160]
                    break
                row['scheduled_sample'] = i
                if not emit(row):
                    status = 'output-cap'
                    break
                recorded += 1
            finish()
        except BaseException as error:
            if not output_failed:
                status = 'observer-failed'
                reason = (type(error).__name__ + ': ' + str(error)).encode('ascii', 'replace').decode()[:160]
                finish()
            raise
        finally:
            # Keep partial evidence on failure; a write/fsync error is never success.
            os.fsync(stream.fileno())
            fsync_parent(output)
    return {'status': status, 'bytes': used, 'samples_recorded': recorded, 'missed_slots': missed}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', required=True)
    parser.add_argument('--contract-sha256', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    c = load_contract(args.contract, args.contract_sha256)
    result = run(c, args.output, args.contract_sha256)
    print(json.dumps(result, sort_keys=True))
    if result['status'] == 'observation-stopped':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
