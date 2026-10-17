#!/usr/bin/env python3
"""Reuse pinned packet65 binaries/fixtures and prepare immutable packet70 views. No execution."""
import argparse
import json
import os
from pathlib import Path
import shutil
from storage import digest as sha
from bundle_selection import EXPERTS
P = Path(__file__).resolve().parent
ROOT = P.parents[3]
BASE = P.parent / 'packet65-expert-occupancy'
PRESET = P.parent / 'packet64-record-bundle/selections/1-draft-hc-batch'

def read(path):
    return json.loads(path.read_text())

def save(path, row):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(row, indent=2) + '\n')

def check(root, entries):
    for name, expected in entries.items():
        if sha(root / name) != expected:
            raise ValueError('parent identity changed: ' + str(root / name))

def link(source, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.exists():
        os.link(source.resolve(), dest)
    if sha(source) != sha(dest):
        raise ValueError('existing artifact changed: ' + str(dest))

def prepare():
    build = read(BASE / 'build-device-receipt.json')
    check(ROOT, build['sources']); check(BASE, build['artifacts'])
    copied = {}
    for f in BASE.rglob('*'):
        rel = f.relative_to(BASE)
        if rel.parts[0] in ('build','screen','selections','evidence'):
            continue
        if f.is_file() and f.suffix in ('.cpp','.hpp','.inc','.bf16'):
            if sha(P / rel) != sha(f):
                raise ValueError('copied packet65 source differs: ' + str(rel))
            copied[str((P / rel).relative_to(ROOT))] = sha(f)
    save(P/'binary-reuse.json', dict(passed=True,device_executed=False,compiled=False,
         parent_receipt=str((BASE/'build-device-receipt.json').relative_to(ROOT)),
         parent_receipt_sha256=sha(BASE/'build-device-receipt.json'),
         binaries={str((BASE/name).relative_to(ROOT)):value for name,value in build['artifacts'].items()},
         copied_sources=copied))
    for expert in EXPERTS:
        original = BASE / 'selections' / expert
        parent = read(original / 'screen-seal.json')
        for key, root in (('sources',ROOT),('artifacts',original),('gates',original),('fixture_files',original)):
            check(root,parent[key])
        view = P/'selections'/('1-draft-hc-batch-'+expert)
        view.mkdir(parents=True,exist_ok=True)
        if (view/'screen-seal.json').exists():
            raise ValueError('view already sealed; never overwrite')
        selection = read(PRESET/'selection.json')
        selection['choices']['experts'] = expert
        save(view/'selection.json',selection)
        for name in ('memory-plan.json','dispatch-speed6.json'):
            shutil.copyfile(PRESET/name,view/name)
        for name in (*parent['artifacts'],*parent['fixture_files']):
            link(original/name,view/name)
        for name in parent['gates']:
            (view/name).parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(original/name,view/name)
        audit=read(original/'placement-audit.json')
        audit['schema']='packet70.placement-audit.v1'
        audit['engine_sources'].update(copied)
        save(view/'placement-audit.json',audit)
    # Local CPU-preparation summary is honest about inherited gates, no new native runs.
    save(P/'cpu-validation.json',dict(passed=True,device_executed=False,cpu_model_executed=False,
         scope='Inherited packet64 bundle and packet65 expert CPU gates; local mock checks recorded separately',
         files={str((P/'binary-reuse.json').relative_to(ROOT)):sha(P/'binary-reuse.json'),
                str((BASE/'cpu-validation.json').relative_to(ROOT)):sha(BASE/'cpu-validation.json'),
                str((P.parent/'packet64-record-bundle/cpu-validation.json').relative_to(ROOT)):sha(P.parent/'packet64-record-bundle/cpu-validation.json')}))

def seal():
    from screen_seal_support import wrapper_seal
    wrapper_seal()
    reuse=read(P/'binary-reuse.json'); check(ROOT,reuse['copied_sources']);check(ROOT,reuse['binaries'])
    for expert in EXPERTS:
        original=BASE/'selections'/expert
        row=read(original/'screen-seal.json')
        view=P/'selections'/('1-draft-hc-batch-'+expert)
        if (view/'screen-seal.json').exists():raise ValueError('view already sealed')
        for key,root in (('sources',ROOT),('artifacts',view),('gates',view),('fixture_files',view)):check(root,row[key])
        row['sources'].update(reuse['copied_sources'])
        row['sources'].update({str(f.relative_to(ROOT)):sha(f) for f in
            [*view.glob('*.json'), P/'binary-reuse.json', P/'prepare_packet.py',P/'screen_seal_support.py',
             P/'screen/wrapper-seal.json',*sorted((P/'screen').glob('*.py'))]})
        row.update(selected_experts=expert,packet70_preset='1-draft-hc-batch',
                   qualification='CPU inheritance only; combined packet70 device chain pending')
        save(view/'screen-seal.json',row)
    print('PASS: five packet70 selections; packet65 binary reused; no native execution')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--seal',action='store_true');a=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    assert set(os.sched_getaffinity(0)) <= set(range(8,16))|set(range(24,32))
    seal() if a.seal else prepare()
