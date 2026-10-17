#!/usr/bin/env python3
"""Two fresh CPU-only, full-shape layer comparisons. Never launches device build."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
from preparation import exclusive_cpu_work

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]

def sha(path):
    with Path(path).open('rb') as f: return hashlib.file_digest(f, 'sha256').hexdigest()

def verify(mapping):
    for name, digest in mapping.items():
        if sha(ROOT / name) != digest: raise ValueError('input changed: ' + name)

def main():
    result = dict(schema='ownrt.packet48b.layer-cpu-gate.v1', passed=False,
                  device_executed=False, error=None)
    try:
        with exclusive_cpu_work(planned_write_bytes=256_000_000) as limits:
            build_path = HERE / 'build-layer-host.json'
            build = json.loads(build_path.read_text())
            if build.get('mode') != 'host' or build.get('passed') is not True or build.get('device_executed') is not False:
                raise ValueError('passing host-only build required')
            sources = dict(build['source_hashes']); artifacts = build['artifacts']
            sources[str(Path(__file__).resolve().relative_to(ROOT))] = sha(Path(__file__))
            verify(sources); verify(artifacts)
            binary = HERE / 'build/host/layer-bench'
            if str(binary.relative_to(ROOT)) not in artifacts: raise ValueError('unbound CPU binary')
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S.%fZ')
            output = HERE / 'evidence' / ('cpu-layer-' + stamp)
            output.mkdir(parents=True, exist_ok=False)
            env = dict(os.environ, OMP_NUM_THREADS='2', PYTHONDONTWRITEBYTECODE='1')
            repeats = []
            manifests = []
            for n in (1, 2):
                target = output / f'repeat-{n}'
                command = [str(binary), '--cpu-test', '--mode', 'exact', '--output', str(target)]
                with (output / f'repeat-{n}.log').open('w') as log:
                    subprocess.run(command, check=True, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=1800)
                receipt = json.loads((target / 'receipt.json').read_text())
                if not (receipt.get('passed') is True and receipt.get('cpu_mock') is True and
                        receipt.get('device_executed') is False and receipt.get('safe_to_exit') is True):
                    raise ValueError('CPU owner did not pass and retire safely')
                if receipt.get('checks', 0) <= 0 or any(receipt['route_set_counts'].get(str(layer), 0) < 2 for layer in (3, 4)):
                    raise ValueError('CPU changing-input/state gate incomplete')
                comparisons = target / 'comparisons.jsonl'
                if sha(comparisons) != receipt['exact_output_identity']:
                    raise ValueError('CPU output identity mismatch')
                manifest = json.loads((target / 'exact-capture-manifest.json').read_text())
                rows = [json.loads(line) for line in comparisons.read_text().splitlines()]
                metadata = [{k: v for k, v in row.items() if k not in ('sha256', 'equal')} for row in rows]
                if metadata != manifest or len(rows) != receipt['checks'] or any(r['equal'] is not True for r in rows):
                    raise ValueError('CPU producer/final capture manifest incomplete')
                manifests.append(manifest)
                repeats.append(dict(command=command, receipt=receipt,
                                    files={str(p.relative_to(ROOT)): sha(p) for p in
                                           (target / 'receipt.json', comparisons, target / 'exact-capture-manifest.json')}))
            if manifests[0] != manifests[1] or repeats[0]['receipt']['exact_output_identity'] != repeats[1]['receipt']['exact_output_identity']:
                raise ValueError('fresh CPU process raw-byte repeat differs')
            verify(sources); verify(artifacts)
            frozen = HERE / 'exact-capture-manifest.json'
            frozen.write_text(json.dumps(manifests[0], indent=2) + '\n')
            result.update(passed=True, limits=limits, build_receipt_sha256=sha(build_path),
                          source_hashes=sources, artifacts=artifacts,
                          repeats=repeats,
                          exact_capture_manifest_sha256=sha(frozen),
                          completed_utc=datetime.now(timezone.utc).isoformat())
    except Exception as error:
        result['error'] = str(error)
    (HERE / 'cpu-layer-gates.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('schema', 'passed', 'device_executed', 'error')}))
    if not result['passed']: raise SystemExit(1)

if __name__ == '__main__': main()
