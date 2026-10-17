#!/usr/bin/env python3
"""Run mocked coordinator/parser tests, retaining the exact tested sources."""
import io
import json
from pathlib import Path
import unittest
from preparation import exclusive_cpu_work
from window_support import HERE, REPO, require, sha, save
import test_window

def main():
    with exclusive_cpu_work(1_000_000):
        stream=io.StringIO()
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(test_window))
        out=HERE/'evidence-cpu';out.mkdir(exist_ok=True)
        log=out/'python-tests.log';log.write_text(stream.getvalue())
        sources={str(p.relative_to(REPO)):sha(p) for p in HERE.glob('*.py')}
        row=dict(schema='own-runtime.packet52.python-gates.v1',passed=result.wasSuccessful(),device_executed=False,
                 tests=result.testsRun,sources=sources,log=str(log.relative_to(REPO)),log_sha256=sha(log))
        save(HERE/'python-gates.json',row)
        print(json.dumps(dict(passed=row['passed'],device_executed=False,tests=result.testsRun)))
        require(result.wasSuccessful(),'Python gate failed; see evidence-cpu/python-tests.log')

if __name__ == '__main__':
    main()
