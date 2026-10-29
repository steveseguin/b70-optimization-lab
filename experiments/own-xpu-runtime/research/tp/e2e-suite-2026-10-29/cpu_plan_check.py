#!/usr/bin/env python3
"""CPU-only: build and validate the lab adapter's plan for one arm (no device contact); print each rank's argv/env deltas."""
import importlib.util, json, os, sys
from pathlib import Path
arm, out = sys.argv[1], Path(sys.argv[2])
spec = importlib.util.spec_from_file_location('lab_adapter', Path(__file__).parent / 'lab/adapter6_tp.py')
A = importlib.util.module_from_spec(spec); spec.loader.exec_module(A)
plan = A.build_plan(out / f'plan-{arm}', mini=False, max_new=128, seconds=172800, evidence_output=out / f'evid-{arm}')
A.validate_plan(plan)
for r in range(2):
    argv = A.command(plan, r, 12, 7)
    env = plan['environment'][r]
    keys = {k: env[k] for k in sorted(env) if k.startswith(('ZE_', 'ONEAPI', 'Filter', 'NEO', 'Enable', 'OWNRT_TP', 'OWNRT_NO', 'OWNRT_QSA'))}
    print(json.dumps(dict(arm=arm, rank=r, cards=argv[argv.index('--cards') + 1], tp='--tp-replicate' in argv,
                          context=argv[argv.index('--context') + 1], split=argv[argv.index('--target-split') + 1],
                          prefill='--prefill-rows' in argv, binary=plan['binary_sha256'][:12], env=keys)))
print(json.dumps(dict(candidate_bdfs=plan['candidate_bdfs'], command_sha256=plan['command_sha256'])))
