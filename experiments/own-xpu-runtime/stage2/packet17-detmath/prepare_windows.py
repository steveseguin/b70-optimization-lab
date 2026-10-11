#!/usr/bin/env python3
"""Seal CPU-created inputs for the separately admitted device windows."""
import argparse
import json
from pathlib import Path
import shlex
from device_window import HERE, ROOT, BUILD, sha, save


def relative(path):
    return str(path.resolve().relative_to(ROOT))


def verify_hash_coverage(path, chunk):
    rows = 0
    if not path.is_file():
        return False, rows
    try:
        with path.open() as f:
            for op in (14, 15):
                for start in range(0, 1 << 32, chunk):
                    fields = [int(v) for v in next(f).split()]
                    if len(fields) != 5 or fields[:3] != [op, start, min(chunk, (1 << 32) - start)]:
                        return False, rows
                    if any(not 0 <= v < 1 << 64 for v in fields[3:]):
                        return False, rows
                    rows += 1
            if f.read().strip():
                return False, rows
    except (StopIteration, ValueError):
        return False, rows
    return True, rows


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--census-binary', type=Path, required=True)
    p.add_argument('--fixture-binary', type=Path, required=True)
    p.add_argument('--fixtures', type=Path, required=True)
    p.add_argument('--fixture-trace', type=Path, required=True)
    p.add_argument('--trace-receipt', type=Path, required=True)
    p.add_argument('--host-hashes', type=Path, required=True)
    p.add_argument('--cpu-receipt', type=Path, required=True)
    p.add_argument('--oracle-receipt', type=Path, default=HERE / 'oracle-build-receipt.json')
    p.add_argument('--authority', default='packet17-core-on-device-v2')
    p.add_argument('--chunk', type=int, default=262144)
    a = p.parse_args()
    if not 64 <= a.chunk <= 262144 or a.chunk % 64:
        raise SystemExit('chunk must be a multiple of 64, at most 262144')
    cases = (a.fixtures / 'cases.txt').read_text().splitlines()
    if len(cases) != 72 or len(set(cases)) != 72:
        raise SystemExit('exactly 72 unique fixtures required')
    cpu = json.loads(a.cpu_receipt.read_text())
    trace = json.loads(a.trace_receipt.read_text())
    # These explicit summary keys are written by the packet build after the
    # underlying per-case GNU and IntelLLVM comparisons have finished.
    passed = cpu.get('parallel_vs_core_gnu') == 72 and cpu.get('parallel_vs_core_intel') == 72 and cpu.get('core_gnu_vs_intel') == 72
    trace_complete = trace.get('cases') == cases and trace.get('complete') is True and trace.get('trace_sha256') == sha(a.fixture_trace)
    if a.fixture_trace.stat().st_size == 0 or a.fixture_trace.stat().st_size % 16:
        raise SystemExit('invalid fixture trace')
    complete, rows = verify_hash_coverage(a.host_hashes, a.chunk)
    paths = set(p for p in HERE.rglob('*') if p.is_file() and BUILD not in p.parents and '.git' not in p.parts)
    oracle = json.loads(a.oracle_receipt.read_text())
    for name, digest in oracle['sources'].items():
        path = ROOT / name
        if sha(path) != digest:
            raise SystemExit('oracle source identity changed: ' + name)
        paths.add(path)
    # Use compiler-produced transitive include lists, not a hand-maintained list
    # that can silently miss an owner, shared kernel or generated table header.
    dependency_files = sorted((BUILD / 'native').rglob('*.o.d'))
    if not dependency_files:
        raise SystemExit('native compiler dependency records missing')
    for dependency in dependency_files:
        text = dependency.read_text().replace('\\\n', ' ')
        for word in shlex.split(text.partition(':')[2]):
            path = Path(word).resolve()
            if ROOT in path.parents:
                paths.add(path)
    for name in ('owner.cpp', 'owner.hpp', 'sycl_device.cpp', 'sycl_operation.hpp'):
        paths.add(HERE.parent.parent / 'stage1/packet3-prep/src' / name)
    paths.update(a.fixtures / name for name in cases)
    paths.update(a.fixtures / (name + '.core') for name in cases)
    paths.update([a.fixtures / 'cases.txt', a.census_binary, a.fixture_binary, a.fixture_trace, a.trace_receipt, a.cpu_receipt])
    if a.host_hashes.is_file():
        paths.add(a.host_hashes)
    if Path(str(a.host_hashes) + '.sanity.json').is_file():
        paths.add(Path(str(a.host_hashes) + '.sanity.json'))
    wa_receipt = HERE / 'wa-reference-receipt.json'
    wa = json.loads(wa_receipt.read_text()) if wa_receipt.exists() else None
    wa_hashes = {}
    if wa:
        from prepare_wa import input_identity, validate_index
        if wa.get('complete') is not True or wa['generator']['inputs'] != input_identity():
            raise SystemExit('W-A reference inputs changed')
        validate_index(BUILD / 'wa-reference', a.chunk)
        for name, digest in wa['hashes'].items():
            path = HERE / name
            if sha(path) != digest:
                raise SystemExit('W-A reference changed: ' + name)
            wa_hashes[relative(path)] = digest
        paths.add(BUILD / 'census-plain-link-control')
        paths.add(BUILD / 'precision-link-control.json')
    record = dict(wa_host_references_complete=bool(wa), wa_reference_hashes=wa_hashes,
                  wa_reference_dir=relative(BUILD / 'wa-reference'),
                  precision_control_binary=relative(BUILD / 'census-plain-link-control'),
                  schema='own-runtime.packet17.prepared-window.v2', compiled=True,
                  device_executed=False, chunk=a.chunk, native_bits=32,
                  host_hashes_complete=complete, host_hash_rows=rows,
                  cpu_three_way_passed=passed, fixture_trace_complete=trace_complete,
                  census_binary=relative(a.census_binary), fixture_binary=relative(a.fixture_binary),
                  fixtures=relative(a.fixtures), fixture_trace=relative(a.fixture_trace),
                  host_hashes=relative(a.host_hashes), cases=cases, authority=a.authority,
                  hashes={relative(path): sha(path) for path in sorted(paths)})
    save(BUILD / 'window-prepared.json', record)
    print(json.dumps({k: record[k] for k in ('device_executed', 'host_hashes_complete', 'cpu_three_way_passed', 'fixture_trace_complete')}))


if __name__ == '__main__':
    main()
