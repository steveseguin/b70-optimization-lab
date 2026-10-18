#!/usr/bin/env python3
"""Use the unchanged shared submission CLI with packet56's strict lineage checks.

Only the packet49 evidence validator dependency is replaced, with its local
extension that adds the sealed packet56 prefix. The shared preflight, API shape,
quality requirements and posting implementation execute unchanged.
"""
import importlib.util
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(P))
import packet56_submission


def load_submitter():
    name = '_packet56_shared_submission_cli'
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts/submit_localmaxxing_results.py')
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get('packet49_submission')
    try:
        # The original CLI imports these functions once at module load. They
        # retain their strict local pin/evidence verification after restoration.
        sys.modules['packet49_submission'] = packet56_submission
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop('packet49_submission', None)
        else:
            sys.modules['packet49_submission'] = previous
    assert module.is_packet49 is packet56_submission.is_packet49
    assert module.packet49_scope_problems is packet56_submission.scope_problems
    return module


if __name__ == '__main__':
    raise SystemExit(load_submitter().main())
