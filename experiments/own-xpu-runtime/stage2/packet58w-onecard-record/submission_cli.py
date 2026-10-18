#!/usr/bin/env python3
"""Shared LocalMaxxing CLI with packet58s's strict offline evidence validator.

Copied/adapted from packet91/submission_cli.py. Only the lineage validator is
substituted; shared API projection, preflight, dry runs and receipt checks remain.
The coordinator alone invokes real submission. Preparation never invokes this CLI.
"""
import importlib.util
from pathlib import Path
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
sys.path.insert(0, str(P))
import packet58_submission


def load_submitter():
    spec = importlib.util.spec_from_file_location('_packet58s_shared_submission_cli', ROOT / 'scripts/submit_localmaxxing_results.py')
    module = importlib.util.module_from_spec(spec)
    previous = sys.modules.get('packet49_submission')
    try:
        sys.modules['packet49_submission'] = packet58_submission
        spec.loader.exec_module(module)
    finally:
        if previous is None:
            sys.modules.pop('packet49_submission', None)
        else:
            sys.modules['packet49_submission'] = previous
    assert module.is_packet49 is packet58_submission.is_packet49
    assert module.packet49_scope_problems is packet58_submission.scope_problems
    return module


if __name__ == '__main__':
    raise SystemExit(load_submitter().main())
