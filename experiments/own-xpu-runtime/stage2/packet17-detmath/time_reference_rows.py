"""CPU-only v1/v2 reference-row screen; scaling is a risk screen, not GPU timing."""
import hashlib
import json
from pathlib import Path
import statistics
import subprocess
from device_window import sha, save
P = Path(__file__).resolve().parent
B = P / 'build'
ROOT = P.parents[3]
rows = {}
for version in ('v1', 'v2'):
    binary = B / 'native' / ('host-row-' + version)
    deps = subprocess.check_output(['readelf', '-d', str(binary)], text=True)
    if any(x in deps for x in ('libsycl', 'ze_loader', 'OpenCL')):
        raise ValueError('row probe must be CPU-only')
    out = B / ('host-rows-' + version + '.jsonl')
    subprocess.run([str(binary), str(B / 'fixtures'), str(out)], check=True, timeout=600)
    grouped = {}
    for line in out.read_text().splitlines():
        r = json.loads(line)
        grouped.setdefault((r['case'], r['row']), []).append(r['seconds'])
    assert len({case for case, row in grouped}) == 72
    assert all(len(values) == 3 for values in grouped.values())
    rows[version] = grouped
assert rows['v1'].keys() == rows['v2'].keys()
gdn = [statistics.median(values) for (case, row), values in rows['v1'].items()
       if case.startswith(('gdn-', 'gdn-packed-', 'gdn-runtime-f32-')) and not case.startswith('gdn-gated-')]
baseline_cpu = statistics.median(gdn)
snapshot = P.parent / 'packet15-nongemv/before-snapshot.json'
site = json.loads(snapshot.read_text())['non_gemv_sites']['gdn.recurrence']
baseline_device = site['device_ms'] / site['sites'] / 1000
cases = []
for name in sorted({case for case, row in rows['v1']}):
    medians = {v: [statistics.median(values) for (case, row), values in rows[v].items() if case == name] for v in rows}
    cases.append(dict(case=name, rows=len(medians['v1']),
        v1_max_row_median_seconds=max(medians['v1']), v2_max_row_median_seconds=max(medians['v2']),
        v2_to_v1_max_row_median_ratio=max(medians['v2']) / max(medians['v1']),
        scaled_device_seconds_screen_only=max(medians['v2']) / baseline_cpu * baseline_device))
worst = max(cases, key=lambda r: r['scaled_device_seconds_screen_only'])
save(P / 'reference-row-timing.json', dict(device_executed=False, repeats=3, compiler='IntelLLVM 2026.0',
    scope='CPU row timing; median of three fresh-fixture passes for every row; no device duration proof',
    baseline_v1_gdn_cpu_median_seconds=baseline_cpu, baseline_v1_device_seconds=baseline_device,
    baseline_source_sha256=sha(snapshot), worst_screen=worst,
    split_required_by_cpu_screen=worst['scaled_device_seconds_screen_only'] >= 2.5,
    cases=cases, raw_sha256={v: sha(B / ('host-rows-' + v + '.jsonl')) for v in rows},
    binaries={v: sha(B / 'native' / ('host-row-' + v)) for v in rows},
    sources={str(f.relative_to(ROOT)):sha(f) for f in
        (P/'host_row_timing.cpp', P/'time_reference_rows.py', P/'reference.hpp', P/'core_v2.hpp',
         P.parent/'packet15-nongemv/reference.hpp', P.parent/'packet4/core.hpp')}))
print(json.dumps(worst, indent=2))
if worst['scaled_device_seconds_screen_only'] >= 2.5:
    raise SystemExit('CPU screen suggests a reference row needs splitting before admission')
