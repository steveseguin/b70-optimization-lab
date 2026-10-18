#!/usr/bin/env python3
"""CPU-only, immutable packet65 selection views admitted by the v3 contract."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
sys.path.insert(0, str(P / 'screen'))
from common import read, require, save, sha, verify_map
from conditions import cpu_gate
from cpu_seal import verify as verify_wrapper

CHOICES = ('production', 'wg64', 'wg128', 'prefetch64', 'wide64')


def link(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        require(sha(source) == sha(target), 'existing artifact changed: '+str(target))
    else:
        os.link(source, target)


def create(fixture_root):
    cpu_gate()
    verify_wrapper()
    parent_build = read(P / 'build-device-receipt.json')
    require(parent_build['passed'] is True and parent_build['device_executed'] is False, 'CPU build required')
    verify_map(ROOT, parent_build['sources'])
    verify_map(P, parent_build['artifacts'])
    fixture = read(fixture_root / 'receipt.json')
    require(fixture['passed'] is True and fixture['device_executed'] is False and len(fixture['runs']) == 2,
            'two CPU byte fixture lifetimes required')
    verify_map(ROOT, fixture['sources'])
    for index, row in enumerate(fixture['runs'], 1):
        require(row['native']['passed'] is True and row['native']['cases'] == 72, 'full CPU fixture required')
        for name, key in (('expected.bin','expected_sha256'),('candidate.bin','candidate_sha256'),('cases.jsonl','cases_sha256')):
            require(sha(fixture_root / f'repeat-{index}' / name) == row[key], 'fixture file changed')
        require(row['expected_sha256'] == row['candidate_sha256'] == fixture['runs'][0]['candidate_sha256'],
                'CPU byte identity/repeat failed')
    evidence = P / 'evidence/cpu-byte-fixture'
    evidence.mkdir(parents=True, exist_ok=True)
    for name in ('receipt.json', 'compile.log', 'dependencies.d'):
        shutil.copyfile(fixture_root/name, evidence/name)
    for index in (1,2):
        dest = evidence / f'repeat-{index}'
        dest.mkdir(exist_ok=True)
        for name in ('cases.jsonl','native.json','run.log'):
            shutil.copyfile(fixture_root/f'repeat-{index}'/name, dest/name)
    # Original generic sealer remains unmodified. Its schema is the wrapper ABI.
    spec = importlib.util.spec_from_file_location('packet65_generic_seal', P.parent / 'screen/seal.py')
    generic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generic)
    base_selection = read(P/'selection.json')
    require(base_selection['choices']['experts'] == 'production', 'default must stay production')
    extra = {path for path in (P/'seal_selections.py', P/'expert_composition.py', P/'composition_campaign.py', P/'test_expert_composition.py',
             P/'screen/placement-validation/wrapper-seal.json', P/'build-device-receipt.json', evidence/'receipt.json')}
    extra.update((P/'screen').glob('*.py'))
    extra.update((P/'screen').glob('*.json'))
    extra.add(P/'screen/placement-jobs.txt')
    extra.add(P.parent/'screen/seal.py')
    extra.update(P.parent/'packet64-record-bundle'/name for name in ('lane_admission.py','chain_devices.py'))
    for name in ('engine-integration.json','selection-tests.json'):
        gate = read(P/'evidence'/name)
        require(gate['passed'] is True and gate['device_executed'] is False, 'host integration/selection gate failed')
        extra.add(P/'evidence'/name)
    for choice in CHOICES:
        dest = P / 'selections' / choice
        require(not (dest/'screen-seal.json').exists(), 'sealed selection view already exists: '+choice)
        dest.mkdir(parents=True,exist_ok=True)
        selection = json.loads(json.dumps(base_selection))
        selection['choices']['experts'] = choice
        if (dest/'selection.json').exists():
            require(read(dest/'selection.json') == selection, 'unsealed selection differs: '+choice)
        save(dest/'selection.json', selection)
        for name in ('dispatch-speed6.json','memory-plan.json'):
            shutil.copyfile(P/name, dest/name)
        for name in ('build/device/own-rt-iq3','build/gnu-host/own-rt-iq3'):
            link(P/name, dest/name)
        for name in ('expected.bin','candidate.bin'):
            link(fixture_root/'repeat-1'/name, dest/'fixture'/name)
        sources = dict(parent_build['sources'], **fixture['sources'])
        sources.update({str(path.relative_to(ROOT)):sha(path) for path in extra})
        engine = {str((P/name).relative_to(ROOT)):sha(P/name)
                  for name in ('main.cpp','rank.hpp','mtp.hpp','p56_config.hpp','p56_prefix.hpp','p65_attribution.hpp','p65_expert.hpp')}
        save(dest/'placement-audit.json', dict(schema='packet65.placement-audit.v1',
             placement='1', draft_rank=1, target_split=0, target_layers=[24,24],
             dispatch_sha256=sha(dest/'dispatch-speed6.json'), binary_sha256=sha(dest/'build/device/own-rt-iq3'),
             engine_sources=engine, rationale='packet64 24/24 rank1 draft placement; changed target expert kernels independent of layer boundary; device exactness pending'))
        for name in ('selection.json','dispatch-speed6.json','memory-plan.json','placement-audit.json'):
            sources[str((dest/name).relative_to(ROOT))] = sha(dest/name)
        build_path, fixture_path = dest/'build-receipt.json', dest/'byte-fixture.json'
        save(build_path, dict(schema='packet65.selection.cpu-build.v1', passed=True, device_executed=False,
             sources=sources, artifacts={name:sha(dest/name) for name in parent_build['artifacts']},
             parent_build_receipt_sha256=sha(P/'build-device-receipt.json'), selected_experts=choice))
        save(fixture_path, dict(schema='own-runtime.screen.byte-fixture.v1', passed=True, device_executed=False,
             changed_class='production target routed experts; all four selectable occupancy candidates',
             selected_experts=choice, command=fixture['compile_command'],
             execution_command=[str(fixture_root/'p65_cpu'), str(fixture_root/'repeat-1')],
             build_receipt_sha256=sha(build_path), sources=fixture['sources'],
             retained_cpu_receipt=str(evidence.relative_to(ROOT)/'receipt.json'), retained_cpu_receipt_sha256=sha(evidence/'receipt.json'),
             expected=dict(path='fixture/expected.bin',sha256=sha(dest/'fixture/expected.bin')),
             actual=dict(path='fixture/candidate.bin',sha256=sha(dest/'fixture/candidate.bin')),
             fresh_cpu_repeats=2, cases_per_repeat=72, device_exactness='pending packet49 screen'))
        seal_path = dest/'screen-seal.json'
        generic.create(dest,'tp2',build_path,fixture_path,dest/'build/device/own-rt-iq3',dest/'dispatch-speed6.json',seal_path)
        seal = read(seal_path)
        for name in ('engine-integration.json','selection-tests.json'):
            shutil.copyfile(P/'evidence'/name, dest/name)
            seal['gates'][name] = sha(dest/name)
        seal.update(timing_modes=['token','attribution'], selected_experts=choice,
                    attribution='packet65 event observation in full 24/24 production layer composition; fixtures9-16 only')
        save(seal_path, seal)
    return dict(passed=True, device_executed=False, choices=list(CHOICES),
                wrapper_seal_sha256=sha(P/'screen/placement-validation/wrapper-seal.json'))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture-root', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(create(args.fixture_root.resolve()), indent=2))
