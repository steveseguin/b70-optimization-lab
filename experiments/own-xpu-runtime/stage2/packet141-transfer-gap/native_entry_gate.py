"""Run the device binary's real rank argv up to (but never into) device APIs."""
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile
from build_engine import P, B, sha, save, limits


def main():
    limits()
    evidence = P / 'evidence/repair141b'
    receipt = json.loads((P / 'build-receipt.json').read_text())
    cmd = next(r['command'] for r in receipt['commands'] if r['name'] == 'device-entry')
    assert '-fsycl' in cmd and not any('OWN_RT_HOST_ONLY' in x for x in cmd)
    runs = []
    for rank in (0, 1):
        source = P / f'evidence/probe-B/run/ranks/rank{rank}-launch.json'
        launch = json.loads(source.read_text())
        argv = launch['argv'] + ['--p141-cpu-entry-gate']
        trace = evidence / f'native-rank{rank}.strace'
        cp = subprocess.run(['/usr/bin/strace', '-f', '-e', 'trace=open,openat,ioctl',
                             '-o', str(trace), *argv], env=launch['environment'],
                            stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=30)
        (evidence / f'native-rank{rank}.log').write_text(cp.stdout + cp.stderr)
        assert cp.returncode == 0, cp.stderr
        row = json.loads(cp.stdout)
        assert row['passed'] and row['rank'] == rank and row['card'] == rank
        assert row['selection_sha256'] == sha(P / 'selection.json')
        assert not row['device_api_called'] and not row['device_executed'] and not row['model_read']
        text = trace.read_text()
        assert '/dev/dri/' not in text and '.gguf"' not in text and '/dev/accel/' not in text
        assert 'libumf.so.1' in text and 'libur_adapter_level_zero.so.0' in text
        negatives = []
        for name in ('authorization', 'selection-hash', 'context'):
            bad = argv.copy()
            if name == 'authorization': bad.remove('--authorized-device-window')
            if name == 'selection-hash': bad[bad.index('--selection-sha256') + 1] = '0' * 64
            if name == 'context': bad[bad.index('--context') + 1] = '256'
            result = subprocess.run(bad, env=launch['environment'], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == 1 and result.stderr.strip(), (name, result)
            negatives.append(dict(case=name, returncode=result.returncode, error=result.stderr.strip()))
        # Exercise the actual rank exception handler before weights or devices.
        # Old code wrote a receipt but left rank*.log silent on this failure.
        with tempfile.TemporaryDirectory(prefix='p141-rank-error-') as temp:
            bad = launch['argv'].copy()
            bad[bad.index('--native-nice') + 1] = '19'
            bad[bad.index('--output') + 1] = str(Path(temp) / 'rank')
            bad[bad.index('--shared') + 1] = str(Path(temp) / 'missing-shared.bin')
            result = subprocess.run(bad, env=launch['environment'], stdin=subprocess.DEVNULL,
                                    capture_output=True, text=True, timeout=30)
            assert result.returncode == 1 and f'rank {rank} failure: shared open' in result.stderr
            failure = json.loads((Path(temp) / 'rank/receipt.json').read_text())
            assert failure['error'] == 'shared open' and failure['teardown'] == []
            (evidence / f'rank{rank}-early-exception.log').write_text(result.stdout + result.stderr)
        runs.append(dict(rank=rank, argv=argv, launch_sha256=sha(source), result=row,
                         stderr=cp.stderr, negatives=negatives, early_exception=failure,
                         trace_sha256=sha(trace)))
    save(evidence / 'native-entry.json', dict(passed=True, device_executed=False,
         model_read=False, binary_sha256=sha(B / 'device/own-rt-iq3'),
         build_receipt_sha256=sha(P / 'build-receipt.json'), device_compile_command=cmd,
         rank_execs=runs, max_child_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
         limitation='Stops before model and first device API; GPU success remains unmeasured.'))
    print('Real device argv x2, shared selection validation, adapter dependency load, six refusals PASS; no device/model opens')


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (4 * 1024**3, 4 * 1024**3))
    main()
