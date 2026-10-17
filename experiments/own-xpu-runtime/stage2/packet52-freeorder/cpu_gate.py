#!/usr/bin/env python3
"""Fresh-process, bounded CPU arithmetic checks. Never invokes a device binary."""
import json
import os
from pathlib import Path
import subprocess
import time
from preparation import exclusive_cpu_work
from summarize import VARIANTS, CLASSES
from window_support import HERE, REPO, require, sha, save, verify_files


def main():
    with exclusive_cpu_work(8_000_000) as admission:
        save(HERE/'cpu-gates.json', dict(passed=False, device_executed=False, status='in progress; no result yet'))
        build = json.loads((HERE/'build-host.json').read_text())
        require(build.get('passed') is True and build.get('device_executed') is False and build.get('mode') == 'host', 'host build required')
        verify_files(build['source_hashes'], REPO)
        verify_files(build['artifacts'], REPO)
        binary = HERE/'build/host/freeorder-bench'
        expected = {str(binary.relative_to(REPO)): sha(binary)}
        require(build['artifacts'] == expected, 'host binary differs')
        runs = []
        stamp = str(time.time_ns())
        intel = json.loads((HERE/'build-intel-host.json').read_text())
        require(intel.get('passed') is True and intel.get('device_executed') is False and intel.get('mode') == 'intel-host', 'Intel host build required')
        verify_files(intel['source_hashes'], REPO)
        verify_files(intel['artifacts'], REPO)
        intel_binary = HERE/'build/intel-host/freeorder-bench'
        require(intel['artifacts'] == {str(intel_binary.relative_to(REPO)):sha(intel_binary)}, 'Intel host binary differs')
        for compiler_mode in ('host','intel-host'):
            test_binary = HERE/'build'/compiler_mode/'freeorder-bench'
            for repeat in range(2):
                out = HERE/'evidence-cpu'/(compiler_mode+'-'+stamp+'-'+str(repeat))
                out.mkdir(parents=True)
                command = [str(test_binary), '--mode', 'cpu', '--output', str(out)]
                start = time.monotonic()
                with (out/'native.log').open('w') as log:
                    result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                            env={**os.environ, 'OMP_NUM_THREADS':'1'}, timeout=600)
                require(result.returncode == 0, 'CPU arithmetic process failed; retain '+str(out))
                receipt = json.loads((out/'receipt.json').read_text())
                require(receipt.get('passed') is True and receipt.get('mode') == 'cpu'
                        and receipt.get('device_executed') is False and receipt.get('safe_to_exit') is True,
                        'CPU gate/teardown failed')
                rows = [json.loads(line) for line in (out/'comparisons.jsonl').read_text().splitlines()]
                expected_cases = {(t,k,v) for t,k in ((22,2560),(20,640),(14,2560),(14,6144),(8,10240),(8,320),(0,2560)) for v in VARIANTS}
                observed = {(r['type'],r['k'],r['variant']) for r in rows}
                require(observed == expected_cases and len(rows) == len(expected_cases) == receipt['checks']
                        and all(r.get('equal') is True and r.get('sha256') == r.get('cpu_sha256')
                                and r.get('bytes',0) > 0 for r in rows), 'CPU comparisons incomplete')
                files = {str(p.relative_to(REPO)):sha(p) for p in out.iterdir() if p.is_file()}
                runs.append(dict(compiler=compiler_mode, binary_sha256=sha(test_binary), repeat=repeat, command=command, elapsed_seconds=time.monotonic()-start,
                                 output=str(out.relative_to(REPO)), files=files, checks=len(rows),
                                 comparisons_sha256=sha(out/'comparisons.jsonl')))
        require(len({r['comparisons_sha256'] for r in runs}) == 1, 'fresh/cross-compiler CPU output mismatch')
        full_runs = []
        spec = json.loads((HERE/'manifest.json').read_text())
        for repeat in range(2):
            out = HERE/'evidence-cpu'/('full-host-'+stamp+'-'+str(repeat))
            out.mkdir(parents=True)
            command = [str(binary), '--mode', 'cpu-full', '--output', str(out)]
            start = time.monotonic()
            with (out/'native.log').open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT,
                                        env={**os.environ, 'OMP_NUM_THREADS':'1'}, timeout=600)
            require(result.returncode == 0, 'full CPU harness failed; retain '+str(out))
            receipt = json.loads((out/'receipt.json').read_text())
            require(receipt.get('passed') is True and receipt.get('mode') == 'cpu-full'
                    and receipt.get('device_executed') is False and receipt.get('safe_to_exit') is True,
                    'full CPU gate/teardown failed')
            rows = [json.loads(line) for line in (out/'comparisons.jsonl').read_text().splitlines()]
            expected_cases = {(c,v,1,0,0) for c in CLASSES for v in ('control',*VARIANTS)}
            observed = {(r['class'],r['variant'],r['m'],r['token_row'],r['iteration']) for r in rows}
            require(observed == expected_cases and len(rows) == len(expected_cases) == receipt['checks']
                    and all(r.get('equal') is True and r.get('sha256') == r.get('cpu_sha256')
                            and r.get('bytes') == spec['expected_bytes'][r['class']]
                            and r.get('buffers') == spec['expected_buffers'][r['class']] for r in rows),
                    'full CPU case/capture census differs')
            files = {str(p.relative_to(REPO)):sha(p) for p in out.iterdir() if p.is_file()}
            full_runs.append(dict(repeat=repeat, command=command, elapsed_seconds=time.monotonic()-start,
                                  output=str(out.relative_to(REPO)), files=files, checks=len(rows),
                                  comparisons_sha256=sha(out/'comparisons.jsonl')))
        require(full_runs[0]['comparisons_sha256'] == full_runs[1]['comparisons_sha256'], 'fresh full CPU output mismatch')
        row = dict(schema='own-runtime.packet52.cpu-gates.v1', passed=True, device_executed=False,
                   build_receipt_sha256=sha(HERE/'build-host.json'), intel_build_receipt_sha256=sha(HERE/'build-intel-host.json'), artifacts={**expected,**intel['artifacts']},
                   sources={str((HERE/'cpu_gate.py').relative_to(REPO)):sha(HERE/'cpu_gate.py')},
                   admission=admission, runs=runs, full_runs=full_runs,
                   scope='bounded real-K independent CPU traversals and full-shape M1 fixture; device and M2 exactness remain E gates')
        save(HERE/'cpu-gates.json', row)
        print(json.dumps(dict(passed=True, device_executed=False, checks_per_process=runs[0]['checks'],
                              seconds=[r['elapsed_seconds'] for r in runs], full_checks_per_process=full_runs[0]['checks'], full_seconds=[r['elapsed_seconds'] for r in full_runs])))

if __name__ == '__main__':
    main()
