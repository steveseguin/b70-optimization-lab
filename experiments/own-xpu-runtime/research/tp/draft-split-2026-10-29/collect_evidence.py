#!/usr/bin/env python3
"""Copy the small evidence files of rank-harness run directories into evidence/<run>/ (state bundles stay in the archive).
Usage: collect_evidence.py RUNS_DIR NAME... [--no-state]"""
import shutil, sys
from pathlib import Path
D = Path(__file__).resolve().parent
args = [a for a in sys.argv[1:] if not a.startswith('--')]; state = '--no-state' not in sys.argv
runs = Path(args[0])
FILES = ['summary.json', 'rank{r}.log', 'rank{r}/draft-head-split.json', 'rank{r}/draft-final-state/all-state.json',
         'rank{r}/draft-final-state/draft-head-split-exchange.json', 'rank{r}/tp-exchange.json', 'rank{r}/tp-replicate-compare.json',
         'rank{r}/draft-prefix.json', 'rank{r}/draft-head-raw.json', 'rank{r}/census.json', 'rank{r}/tp-plan.json']
for name in args[1:]:
    r = '0' if (runs / name / 'rank0').exists() else '1'
    files = FILES + (['rank{r}/state-2147483647/state.json'] if state else [])
    for f in files:
        src = runs / name / f.format(r=r)
        if src.exists():
            dst = D / 'evidence' / name / f.format(r=r); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(src, dst)
    print(name, sum(1 for _ in (D / 'evidence' / name).rglob('*') if _.is_file()), 'files')
