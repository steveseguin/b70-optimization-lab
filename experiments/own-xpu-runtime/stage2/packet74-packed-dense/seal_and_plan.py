"""Reseal only the screen admission repair; keep engine and selection bytes fixed."""
import importlib.util
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

P = Path(__file__).resolve().parent
sys.path.insert(0, str(P / 'screen'))
from common import ROOT, read, require, save, sha, verify_map
from conditions import cpu_gate


def main():
    cpu_gate()
    screen = P / 'screen'
    archive = P / 'evidence/admission-repair/before'
    require(not archive.exists(), 'repair already archived; do not overwrite evidence')
    views = sorted((P / 'selections').glob('*/screen-seal.json'))
    require(views, 'selection seals required')
    unchanged = {}
    for seal in views:
        row = read(seal)
        verify_map(seal.parent, row['artifacts'])
        for name in (*row['artifacts'], 'selection.json', 'dispatch-speed6.json',
                     'memory-plan.json', 'placement-audit.json'):
            path = seal.parent / name
            unchanged[str(path.relative_to(ROOT))] = sha(path)
        for name in ('screen-seal.json', 'build-receipt.json', 'byte-fixture.json'):
            dest = archive / seal.parent.relative_to(P) / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(seal.parent / name, dest)
    shutil.copytree(screen / 'placement-validation', archive / 'placement-validation')
    for name in ('parent-wrapper.json', 'wrapper-seal.json'):
        shutil.copyfile(screen / name, archive / name)

    # Refresh only the adopted v4 delta, preserving unrelated historical pins.
    parent = read(screen / 'parent-wrapper.json')
    source = ROOT / parent['source']
    for name in ('lane_admission.py', 'screen.py', 'wrapper-seal.json'):
        parent['pins'][str((source / name).relative_to(ROOT))] = sha(source / name)
    parent['pins'][str((source / 'test_plan_admission.py').relative_to(ROOT))] = sha(source / 'test_plan_admission.py')
    save(screen / 'parent-wrapper.json', parent)
    (screen / 'placement-validation/wrapper-seal.json').unlink()
    subprocess.run([sys.executable, '-B', str(screen / 'cpu_seal.py')],
                   stdin=subprocess.DEVNULL, check=True)
    shutil.copyfile(screen / 'placement-validation/wrapper-seal.json', screen / 'wrapper-seal.json')
    subprocess.run([sys.executable, '-B', str(screen / 'quick_seal.py')],
                   stdin=subprocess.DEVNULL, check=True)

    spec = importlib.util.spec_from_file_location('generic_screen_seal', P.parent / 'screen/seal.py')
    generic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generic)
    allowed = {str((screen / name).relative_to(ROOT)) for name in
               ('lane_admission.py', 'screen.py', 'placement-validation/wrapper-seal.json')}
    for seal in views:
        view = seal.parent
        build = read(view / 'build-receipt.json')
        fixture = read(view / 'byte-fixture.json')
        # Every engine/fixture source must still match; only the named wrapper
        # repair may change. No recompile, fixture rerun or selector rewrite.
        verify_map(ROOT, {p: digest for p, digest in build['sources'].items() if p not in allowed})
        verify_map(ROOT, fixture['sources'])
        for path in allowed | {str((screen / 'test_plan_admission.py').relative_to(ROOT)),
                               str((screen / 'parent-wrapper.json').relative_to(ROOT)),
                               str(Path(__file__).resolve().relative_to(ROOT))}:
            build['sources'][path] = sha(ROOT / path)
        save(view / 'build-receipt.json', build)
        fixture['build_receipt_sha256'] = sha(view / 'build-receipt.json')
        save(view / 'byte-fixture.json', fixture)
        seal.unlink()
        generic.create(view, 'tp2', view / 'build-receipt.json', view / 'byte-fixture.json',
                       view / 'build/device/own-rt-iq3', view / 'dispatch-speed6.json', seal)
    verify_map(ROOT, unchanged)

    queue = P.parents[1] / 'ops/lane-queue'
    packet = P.name.split('-')[0].replace('packet', 'p')
    with tempfile.TemporaryDirectory(prefix=packet + '-admission-plan-') as temp:
        dest = Path(temp)
        proposal = queue / ('proposed-' + packet + '-A.txt')
        shutil.copyfile(proposal, dest / proposal.name)
        shutil.copyfile(proposal, dest / 'queue-A.txt')
        command = [sys.executable, '-B', str(queue / 'lanequeue.py'), 'plan',
                   '--lane', 'A', '--directory', str(dest)]
        result = subprocess.run(command, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=180)
        (archive.parent / 'lanequeue-plan-A.log').write_text(result.stdout + result.stderr)
        require(result.returncode == 0, 'queue plan failed; inspect admission-repair log')
    save(archive.parent / 'result.json', dict(passed=True, device_executed=False,
         binaries_and_selections_unchanged=unchanged, selection_seals=len(views),
         queue_plan='passed', wrapper_tests='passed'))
    print(f'{packet}: wrapper, {len(views)} selection seals and lane-A queue plan PASS')


if __name__ == '__main__':
    main()
