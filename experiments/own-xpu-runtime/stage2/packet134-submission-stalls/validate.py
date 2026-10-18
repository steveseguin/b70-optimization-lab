"""Run analysis gates and retain their CPU-only receipt."""
import contextlib
import json
import os
from pathlib import Path
import resource
import shutil
import time
import unittest

import analyze
import test_analysis

P = Path(__file__).resolve().parent


def main():
    assert os.getpriority(os.PRIO_PROCESS, 0) == 19
    affinity = sorted(os.sched_getaffinity(0))
    assert set(affinity) <= set(range(8, 16)) | set(range(24, 32))
    free_before = shutil.disk_usage('/').free
    assert free_before >= 25_000_000_000
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromModule(test_analysis)
    with (P/'evidence/tests.log').open('w') as log:
        with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    report = dict(schema='packet134.cpu-validation.v1', passed=result.wasSuccessful(),
        tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), nice=os.getpriority(os.PRIO_PROCESS, 0),
        affinity=affinity, stdin_closed=Path('/proc/self/fd/0').resolve() == Path('/dev/null'),
        address_space_cap_bytes=resource.getrlimit(resource.RLIMIT_AS)[0],
        max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        elapsed_seconds=time.monotonic()-started, root_free_before=free_before,
        root_free_after=shutil.disk_usage('/').free, build_bytes=0,
        gpu_executed=False, runtime_changed=False, compiled=False, queue_proposed=False,
        source_sha256={name: analyze.sha(P/name) for name in
            ('analyze.py', 'test_analysis.py', 'validate.py', 'seal.py')},
        report_sha256=analyze.sha(P/'evidence/attribution.json'),
        input_pins_sha256=analyze.sha(P/'input-pins.json'))
    analyze.save(P/'evidence/validation.json', report)
    print(json.dumps(report, sort_keys=True))
    assert result.wasSuccessful(), (P/'evidence/tests.log')
    assert report['stdin_closed'] and report['root_free_after'] >= 25_000_000_000


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (8*1024**3, 8*1024**3))
    main()
