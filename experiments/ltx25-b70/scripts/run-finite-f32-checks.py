#!/usr/bin/env python3
"""Run exact-bit and affected stdlib integration checks, with a fresh receipt."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

SCRIPTS = Path(__file__).resolve().parent
TESTS = ('test-finite-f32-bits.py', 'test-continuation-anchor-io.py',
         'test-continuation-delivery.py', 'test-continuation-anchor-node.py',
         'test-continuation-stream-state.py')
SOURCES = ('finite_f32_bits.py', 'continuation_anchor_io.py', 'continuation_delivery.py',
           'continuation_anchor_node.py', 'bind-continuation-anchor.py',
           'build-continuation-graph.py', 'continuation_stream_state.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    with args.receipt.open('x') as output:
        suites = []
        for index, name in enumerate(TESTS):
            spec = importlib.util.spec_from_file_location(f'finite_candidate_test_{index}', SCRIPTS / name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            suites.append(unittest.defaultTestLoader.loadTestsFromModule(module))
        result = unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(suites))
        report = {'status': 'passed-stdlib-candidate-checks' if result.wasSuccessful() else 'failed',
                  'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                  'source_sha256': {name: hashlib.sha256((SCRIPTS / name).read_bytes()).hexdigest()
                                    for name in SOURCES + TESTS + (Path(__file__).name,)},
                  'gpu_requests': 0, 'torch_imported': 'torch' in sys.modules,
                  'limits': ['Bit-pattern and synthetic integration tests, not new generation',
                             'No native tensor runtime, playback or speed qualification']}
        output.write(json.dumps(report, indent=2) + '\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)


if __name__ == '__main__':
    main()
