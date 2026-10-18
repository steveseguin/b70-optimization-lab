#!/usr/bin/env python3
"""Run only the CPU analysis and link checks, retaining their real outputs."""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def main():
    resource.setrlimit(resource.RLIMIT_AS, (8 * 1024**3, 8 * 1024**3))
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    assert set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32))
    assert shutil.disk_usage(ROOT).free >= 25_000_000_000
    evidence = HERE/'evidence'
    evidence.mkdir(exist_ok=True)
    checks = [
        ('replay', [sys.executable, '-B', str(HERE/'simulate.py'), '--check']),
        ('prior-replay', [sys.executable, '-B', str(HERE/'audit_prior.py'), '--check']),
        ('analysis-tests', [sys.executable, '-B', str(HERE/'test_simulate.py')]),
        ('links', [sys.executable, '-B', str(ROOT/'tools/check-doc-links.py'),
                   *(str(p) for p in sorted(HERE.glob('*.md'))),
                   str(ROOT/'notes/2026-10-18-own-runtime-packet126.md')]),
    ]
    results = []
    for name, command in checks:
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=180)
        log = evidence/(name+'.log')
        log.write_bytes(result.stdout)
        results.append({'name': name, 'argv': command, 'returncode': result.returncode,
                        'elapsed_seconds': time.monotonic()-started,
                        'log': str(log.relative_to(ROOT)),
                        'log_sha256': hashlib.sha256(result.stdout).hexdigest()})
        assert result.returncode == 0, (name, result.stdout.decode())
    drain = json.loads((HERE/'drain-parent.json').read_text())
    assert drain['passed']
    for row in drain['files']:
        assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest() == row['sha256']
    packet_bytes = sum(p.stat().st_size for p in HERE.rglob('*') if p.is_file())
    assert packet_bytes < 250_000_000 and not (HERE/'build').exists()
    report = {'passed': True, 'device_executed': False, 'runtime_implemented': False,
              'runtime_quality_gate': 'not run; implementation not admitted',
              'checks': results, 'parent_drain_passed': True,
              'parent_drain_report_sha256': hashlib.sha256((HERE/'drain-parent.json').read_bytes()).hexdigest(),
              'packet_bytes_before_validation_receipt': packet_bytes,
              'build_bytes': 0, 'root_free_bytes': shutil.disk_usage(ROOT).free,
              'children_max_rss_kib': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
              'cpu_affinity': sorted(os.sched_getaffinity(0)),
              'nice': os.getpriority(os.PRIO_PROCESS, 0), 'cpu_only_address_limit_bytes': 8*1024**3}
    (HERE/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'passed': True, 'checks': len(results),
                      'packet_bytes': packet_bytes, 'root_free_bytes': report['root_free_bytes']}))


if __name__ == '__main__':
    main()
