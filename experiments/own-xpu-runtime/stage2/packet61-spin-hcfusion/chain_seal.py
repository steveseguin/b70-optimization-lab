#!/usr/bin/env python3
"""Add a chain admission seal around immutable screened bytes; never rebuild."""
import argparse
import json
import os
from pathlib import Path
import time

from storage import digest

P = Path(__file__).resolve().parent
ROOT = P.parents[3]
PARENT = P.parent / 'packet56-draft-prefix'
SCREEN = P.parent / 'packet61-spin-hcfusion'
B = P / 'build'


def require(value, message):
    if not value:
        raise ValueError(message)


def check_map(root, entries):
    require(isinstance(entries, dict) and entries, 'empty identity map')
    for name, expected in entries.items():
        require(digest(root / name) == expected, 'sealed bytes changed: ' + str(root / name))


def checked():
    binding = json.loads((P / 'chain-binding.json').read_text())
    require(digest(PARENT / 'build-receipt.json') == binding['parent_seal_sha256'], 'parent seal changed')
    require(digest(SCREEN / 'screen-seal.json') == binding['screen_seal_sha256'], 'screen seal changed')
    for folder,key in (('packet60-hc-fusion','hc_parent_seal_sha256'),('packet56w-spin','spin_parent_seal_sha256')):
        require(digest(P.parent/folder/'screen-seal.json')==binding[key], 'component parent seal changed: '+folder)
    parent = json.loads((PARENT / 'build-receipt.json').read_text())
    screen = json.loads((SCREEN / 'screen-seal.json').read_text())
    require(parent['passed'] is True and parent['device_admission_ready'] is True, 'parent not prepared')
    require(screen['schema'] == 'own-runtime.screen.cpu-seal.v1'
            and screen['passed'] is True and screen['device_executed'] is False
            and screen['profile'] == 'tp2' and screen['arithmetic'] == parent['arithmetic'], 'screen identity')
    check_map(ROOT, parent['sources'])
    check_map(ROOT, screen['sources'])
    check_map(SCREEN, screen['artifacts'])
    check_map(SCREEN, screen['gates'])
    check_map(SCREEN, screen['fixture_files'])
    for name in screen['gates']:
        gate = json.loads((SCREEN / name).read_text())
        require(gate['passed'] is True and gate['device_executed'] is False, 'screen CPU gate incomplete')
    require(screen['fixture_files']['integrated-fixture/combined-actual.bin'] == screen['fixture_files']['integrated-fixture/combined-expected.bin'], 'screen byte fixture differs')
    # Legacy operator fixtures remain packet56; both full engines are packet61.
    # Integrated HC CPU evidence is bound by the screen; device oracle gates stay mandatory.
    artifacts = dict(parent['artifacts_sha256'])
    for name in ('device/own-rt-iq3','gnu-host/own-rt-iq3'):
        artifacts[name] = screen['artifacts']['build/'+name]
    require((B / 'device/own-rt-iq3').resolve() == (SCREEN / 'build/device/own-rt-iq3').resolve(), 'wrong engine target')
    check_map(B, artifacts)
    for name in ('selection.json', 'memory-plan.json', 'mtp-manifest.tsv', 'p56_config.hpp'):
        require(digest(P / name) == digest(SCREEN / name) == digest(PARENT / name), 'inherited configuration changed: ' + name)
    from shared_oracle import static_binding
    require(static_binding() == parent['shared_oracle'], 'shared oracle changed')
    require((B / 'input').resolve() == (PARENT / 'build/input').resolve(), 'input tree changed')
    require(digest(B / 'input/input.json') == parent['input_sha256'], 'input identity changed')
    fixture_manifest = json.loads((P / 'input-fixtures.json').read_text())
    fixture_hashes = {name: item['sha256'] for name, item in fixture_manifest['files'].items()}
    check_map(B / 'fusion-fixtures', fixture_hashes)
    sources = dict(parent['sources'], **screen['sources'])
    for folder,key in (('packet60-hc-fusion','hc_parent_seal_sha256'),('packet56w-spin','spin_parent_seal_sha256')):
        sources[str((P.parent/folder/'screen-seal.json').relative_to(ROOT))]=binding[key]
    sources[str((PARENT / 'build-receipt.json').relative_to(ROOT))] = binding['parent_seal_sha256']
    sources[str((SCREEN / 'screen-seal.json').relative_to(ROOT))] = binding['screen_seal_sha256']
    for path in P.iterdir():
        if path.is_file() and (path.suffix in ('.py', '.sh', '.hpp', '.tsv', '.bf16')
                               or path.suffix == '.json' and path.name not in ('build-receipt.json', 'submission-pins.json')):
            sources[str(path.relative_to(ROOT))] = digest(path)
    for leaf in ('calibration/selection.json', 'calibration/preregistration.json', 'oracle/suite_check.py'):
        sources[str((P / leaf).relative_to(ROOT))] = digest(P / leaf)
    fields = ('passed', 'device_executed', 'arithmetic', 'parent_commit', 'shared_oracle',
              'oracle_inputs_sha256', 'oracle_binary_sha256', 'official_manifest_sha256',
              'memory_plan', 'input_sha256', 'p33_linked_fixture_host_sha256',
              'p49_qsa_fixture_host_sha256', 'p49b_expert_fixture_host_sha256',
              'p49c_fixture_host_sha256', 'p49d_fixture_host_sha256',
              'nongemv_fixture_host_sha256_by_context', 'selection', 'draft_prefix')
    from packet56_submission import SPIN, HC_FUSION
    return dict({key: parent[key] for key in fields}, schema='packet61.chain-cpu-seal.v1',
                runtime_revision=json.loads((P / 'runtime-revision.json').read_text())['runtime_revision'],
                parent_seal_sha256=binding['parent_seal_sha256'],
                screen_seal_sha256=binding['screen_seal_sha256'], controller_spin=SPIN, hc_fusion=HC_FUSION,
                fixture_inputs_sha256=fixture_hashes, sources=sources, artifacts_sha256=artifacts, original_artifacts_sha256=artifacts,
                device_admission_ready=True,
                scope=dict(full_model_qualification='Pending full coordinator chain; screen is diagnostic only',
                           fixture_binaries='Unchanged packet56 fixtures and CPU draft reference',
                           engine='Exact packet61 screen-sealed binary; packet56w waits and packet60 HC arithmetic'))


def verify():
    row = json.loads((P / 'build-receipt.json').read_text())
    require(row == checked(), 'chain source/build binding changed')
    return row


def reseal_wrapper():
    """Owner-authorized input repair; immutable engine/screen seals must agree."""
    from storage import B as output_build, REGISTERED_CHAIN
    require(not (output_build / REGISTERED_CHAIN).exists(), 'registered chain already started')
    path = P / 'build-receipt.json'
    old = json.loads(path.read_text())
    row = checked()
    allowed = {'sources', 'fixture_inputs_sha256'}
    require({k: v for k, v in old.items() if k not in allowed}
            == {k: v for k, v in row.items() if k not in allowed},
            'wrapper reseal cannot change binary, arithmetic, oracle or screen identity')
    wrappers = {'window.py', 'queue_runner.py', 'storage.py', 'prepare_chain.py',
                'prepare_inputs.py', 'check_inputs.py', 'plan_gate.py', 'chain_seal.py',
                'test_queue_runner.py', 'test_check_inputs.py', 'test_packet61.py', 'input-fixtures.json'}
    changed = {name for name in old['sources'].keys() | row['sources'].keys()
               if old['sources'].get(name) != row['sources'].get(name)}
    require(all((ROOT / name).parent == P and Path(name).name in wrappers for name in changed),
            'unexpected source change in wrapper reseal: ' + str(sorted(changed)))
    backup = P / 'evidence' / ('chain-seal-before-input-repair-' + digest(path) + '.json')
    if not backup.exists():
        backup.write_bytes(path.read_bytes())
    path.write_text(json.dumps(row, indent=2) + '\n')
    from packet56_submission import pin_resealed_packet56
    pin_resealed_packet56(repo=ROOT)
    return row


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', action='store_true')
    parser.add_argument('--reseal-wrapper', action='store_true',
                        help='Input repair only; preserve old seal, reject any binary/identity change')
    args = parser.parse_args()
    require(os.getpriority(os.PRIO_PROCESS, 0) == 19, 'nice19 required')
    require(set(os.sched_getaffinity(0)) <= set(range(8, 16)) | set(range(24, 32)), 'CPU helper affinity required')
    start = time.monotonic()
    require(not (args.verify and args.reseal_wrapper), 'choose verify or wrapper reseal')
    if args.reseal_wrapper:
        row = reseal_wrapper()
    elif args.verify:
        row = verify()
    else:
        require(not (P / 'build-receipt.json').exists() and not (B / 'device-cards01-a').exists(), 'never overwrite a seal or started chain')
        row = checked()
        (P / 'build-receipt.json').write_text(json.dumps(row, indent=2) + '\n')
        from packet56_submission import pin_resealed_packet56
        pin_resealed_packet56(repo=ROOT)
    print(json.dumps(dict(passed=True, device_executed=False, seconds=time.monotonic()-start,
                          binary_sha256=row['artifacts_sha256']['device/own-rt-iq3'])))


if __name__ == '__main__':
    main()
