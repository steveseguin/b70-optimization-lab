#!/usr/bin/env python3
"""Seal immutable inputs; submission pins follow the seal to avoid a hash cycle."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
GATES = ('evidence/postload-allocation-cpu.json','evidence/fullshape-submit-cpu.json',
         'evidence/startup-cpu.json','evidence/budget-cpu.json','evidence/python-cpu-gates.json',
         'evidence/submission-58g-dry-run.json','evidence/inherited-byte-gates.json',
         'evidence/readiness-rule-cpu.json','k1-cpu.json')


def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()


def read(p): return json.loads(Path(p).read_text())


def require(ok, why):
    if not ok: raise ValueError(why)


def verify_files(root, files):
    require(bool(files), 'empty source closure')
    for n,h in files.items():
        path = (root/n).resolve()
        require(path.is_relative_to(ROOT) and sha(path) == h, 'changed immutable input: '+n)


def create():
    require(os.getpriority(os.PRIO_PROCESS,0) == 19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(8,16)) | set(range(24,32)), 'helper cores required')
    require(not (P/'evidence/card0-58m-a').exists(), 'never reseal after chain output exists')
    sources, artifacts, gates = {}, {}, {}
    # Bind compiler source closures from copied receipts. Do not pin a changing
    # parent build receipt, readiness report, submission tool or queue output.
    for mode in ('gnu-host','device'):
        r = read(P/f'parent-build-{mode}-receipt.json')
        require(r['passed'] is True and r['device_executed'] is False, 'parent build failed')
        verify_files(ROOT,r['sources_sha256'])
        sources.update(r['sources_sha256'])
        for name,digest in r['binaries'].items():
            if (P/name).exists(): artifacts[name] = digest
    require(len(artifacts) == 5, 'five copied native executables required')
    verify_files(P,artifacts)
    for leaf in GATES:
        r = read(P/leaf)
        require(r.get('passed') is True and r.get('device_executed') is False, 'CPU gate failed: '+leaf)
        pins = r.get('sources',r.get('dependencies',r.get('source_sha256',{})))
        if pins: verify_files(ROOT,pins); sources.update(pins)
        gates[leaf] = sha(P/leaf)
    require(sha(P/'evidence/inherited-byte-gates.json') == read(P/'parent-build-receipt.json')['gates']['evidence/byte-gates.json'],
            'inherited byte gate differs from frozen build snapshot')
    from views import digest
    full = read(P/'evidence/fullshape-submit-cpu.json')
    expected = {(w,m) for w in ('KD','W2m','WS','WS128x','WS128') for m in ('zero-copy','streamed')}
    require(full['checks'] == 10 and {(r['window'],r['miss_path']) for r in full['records']} == expected, 'full-shape coverage')
    for r in full['records']:
        require(r['passed'] and r['legacy_refused'] and r['sites'] == 1486 and r['contexts'] == [32,4096]
                and r['allocation_rows'] == 3446 and r['selection_sha256'] == digest('port')
                and r['arena_totals'] == {'device':24287732980,'host-pinned':48633091712}, 'real-shape proof differs')
    startup = read(P/'evidence/startup-cpu.json')
    require(startup['checks'] == 10 and {(r['window'],r['miss_path']) for r in startup['records']} == expected, 'parser/oracle coverage')
    require(startup['fullshape_receipt_sha256'] == sha(P/'evidence/fullshape-submit-cpu.json'), 'startup proof stale')
    require(sha(P/'selection.json') == digest('port'), 'port selection alias differs')
    require(len(read(P/'evidence/budget-cpu.json')['records']) == 7, 'all seven budgets required')
    require(read(P/'k1-cpu.json')['checks'] == 48, 'both K1 layouts required')
    # Immutable files only. ready.json and submission-pins.json are consumers of
    # this receipt, and chain output never enters its source map.
    excluded = {'build-receipt.json','ready.json','submission-pins.json'}
    for f in [*P.glob('*.py'),*P.glob('*.json'),*(P/'selections').glob('*.json')]:
        if f.name not in excluded: sources[str(f.relative_to(ROOT))] = sha(f)
    for folder in ('evidence/58c-supervisor','evidence/58c-kd'):
        for f in (P/folder).rglob('*'):
            if f.is_file(): sources[str(f.relative_to(ROOT))] = sha(f)
    for n in ('packet56-draft-prefix/p56_head_support.py','packet56-draft-prefix/suite_metrics.py',
              'packet34-replay-bench/window.py','packet49-integrate/oracle/suite_check.py'):
        f = P.parent/n; sources[str(f.relative_to(ROOT))] = sha(f)
    import memory_plan as M
    plan = M.plan(); sources.update(plan['allocation_inventory']['sources'])
    sources[plan['census']['source_path']] = plan['census']['source_sha256']
    sources.update(read(P/'oracle-binding.json')['files_sha256'])
    require(not any('/ops/' in n or n.endswith(('/ready.json','/queue.json','/submission-pins.json')) for n in sources),
            'mutable orchestration in source seal')
    verify_files(ROOT,sources)
    size = sum(f.stat().st_size for f in (P/'build').rglob('*') if f.is_file())
    require(size <= 150_000_000, '150 MB build cap')
    row = dict(schema='own-runtime.packet58.build.v1', passed=True, device_executed=False,
        runtime_revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        arithmetic='iq3-p49-split32-v1', gpu_count=1, decode_mode='plain', views=['port'],
        sources=sources, artifacts=artifacts, gates=gates, retained_build_bytes=size,
        native_recompiled=False, immutable_inputs_only=True,
        qualification='CPU preparation only; screen receipt qualification and device chain remain required')
    (P/'build-receipt.json').write_text(json.dumps(row,indent=2,sort_keys=True)+'\n')
    # One-way binding: code -> build seal -> pins. Both written before the chain.
    submission_sources = {str((P/n).relative_to(ROOT)):sha(P/n) for n in
        ('packet58_submission.py','submission_cli.py','submit_localmaxxing_results.py','suite_metrics.py',
         'receipt_qualification.py','promotion_evidence.py','legacy58g_submission.py')}
    (P/'submission-pins.json').write_text(json.dumps(dict(schema='packet58m.submission-pins.v1',
        build_receipt_sha256=sha(P/'build-receipt.json'), sources=submission_sources,
        artifacts=artifacts, finalized_before_chain=True),indent=2,sort_keys=True)+'\n')
    return row


def main():
    ap = argparse.ArgumentParser(description=__doc__); ap.add_argument('--verify',action='store_true'); args=ap.parse_args()
    if args.verify:
        row = read(P/'build-receipt.json')
        verify_files(ROOT,row['sources']); verify_files(P,row['artifacts']); verify_files(P,row['gates'])
        pins=read(P/'submission-pins.json'); verify_files(ROOT,pins['sources'])
        require(pins['build_receipt_sha256'] == sha(P/'build-receipt.json') and pins['artifacts'] == row['artifacts'], 'submission pins stale')
    else: row=create()
    print(json.dumps(dict(passed=True,device_executed=False,build_bytes=row['retained_build_bytes'],sources=len(row['sources']))))


if __name__ == '__main__': main()
