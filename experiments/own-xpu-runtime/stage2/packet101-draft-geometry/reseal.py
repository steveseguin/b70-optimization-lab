"""CPU-only reseal: retain original gates, detach mutable parent orchestration."""
import importlib.util
import json
import os
from pathlib import Path

from build_engine import P, ROOT, BASE, sha, save, limits, check_map

ROUND = 'reseal-20261018'
DEST = P / 'selections'
PARENT = str(BASE.relative_to(ROOT)) + '/'
BUILD_SOURCES = {
    'compile_turn.py', 'build_engine.py', 'kernel_gate.py', 'math_gate.py',
    'kernel_overlay.py', 'submission_overlay.py', 'bundle_selection.py',
}
BUILD_INPUTS = {
    'engine-commands.json', 'parent-source-manifest.json',
    'build-device-receipt.json', 'rope.bf16', 'mtp-manifest.tsv',
    'selection-template.json', 'dispatch-speed6.json',
}


def parent_policy(path):
    """An allow-list, so new orchestration outputs cannot enter future seals."""
    if not path.startswith(PARENT):
        return 'keep'
    leaf = path[len(PARENT):]
    if leaf == 'evidence/object-identity.json':
        return 'snapshot'
    if leaf.startswith(('evidence/', 'decisions/', 'selections/')):
        return 'exclude'
    if leaf in BUILD_SOURCES or leaf in BUILD_INPUTS:
        return 'keep'
    if Path(leaf).suffix in ('.cpp', '.hpp', '.inc'):
        return 'keep'
    if leaf.startswith('build/') and (Path(leaf).suffix == '.o' or Path(leaf).name == 'own-rt-iq3'):
        return 'keep'
    return 'exclude'


def project_sources(sources):
    bound, excluded, snapshots = {}, {}, {}
    for path, digest in sources.items():
        policy = parent_policy(path)
        if policy == 'exclude':
            excluded[path] = digest
            continue
        if policy == 'snapshot':
            source = ROOT / path
            assert sha(source) == digest, 'build evidence changed: ' + path
            dest = P / 'lineage-inputs' / 'packet97-object-identity.json'
            dest.parent.mkdir(exist_ok=True)
            if not dest.exists():
                dest.write_bytes(source.read_bytes())
            assert sha(dest) == digest
            bound[str(dest.relative_to(ROOT))] = digest
            snapshots[path] = dict(path=str(dest.relative_to(ROOT)), sha256=digest)
        else:
            bound[path] = digest
    check_map(ROOT, bound)
    return bound, excluded, snapshots


def main():
    limits()
    from bootstrap import install
    install()
    spec = importlib.util.spec_from_file_location('p101_reseal_generic', P.parent / 'screen/seal.py')
    generic = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generic)
    rows = []
    for label in ('control', 'draft_attention'):
        old = P / 'selections' / label
        seal = json.loads((old / 'screen-seal.json').read_text())
        check_map(old, seal['gates'])
        check_map(old, seal['artifacts'])
        check_map(old, seal['fixture_files'])
        bound, excluded, snapshots = project_sources(seal['sources'])
        # The only discarded original dependency is an unused audit pin.
        # Actual runtime selection bytes below are copied from this packet.
        assert set(excluded) == {PARENT + 'selection.json'}, excluded
        view = DEST / (label + '-' + ROUND)
        assert not view.exists(), 'fresh sealed directory required: ' + str(view)
        view.mkdir(parents=True)
        for leaf in ('selection.json', 'memory-plan.json', 'dispatch-speed6.json',
                     'placement-audit.json', 'fixture-expected.bin.gz', 'fixture-actual.bin.gz'):
            (view / leaf).write_bytes((old / leaf).read_bytes())
        for relative, digest in seal['artifacts'].items():
            dest = view / relative
            dest.parent.mkdir(parents=True, exist_ok=True)
            os.link(old / relative, dest)
            assert sha(dest) == digest
        # Bind the frozen old receipts as historical evidence, without making
        # their old flattened orchestration closure a live dependency again.
        for leaf in ('screen-seal.json', 'build-receipt.json', 'byte-fixture.json'):
            bound[str((old / leaf).relative_to(ROOT))] = sha(old / leaf)
        for leaf in ('reseal.py', 'screen_jobs_reseal.py', 'screen_job_reseal.py',
                     'queue_plan_reseal.py', 'compare_reseal.py', 'test_reseal.py'):
            bound[str((P / leaf).relative_to(ROOT))] = sha(P / leaf)
        bound[str((view / 'placement-audit.json').relative_to(ROOT))] = sha(view / 'placement-audit.json')
        build = view / 'build-receipt.json'
        save(build, dict(passed=True, device_executed=False, sources=bound,
                         artifacts=seal['artifacts'], original_seal_sha256=sha(old / 'screen-seal.json'),
                         excluded_unused_audit_pins=excluded, local_build_evidence=snapshots,
                         reason='Same binaries, selections and CPU evidence; parent orchestration is not a runtime input.'))
        fixture = json.loads((old / 'byte-fixture.json').read_text())
        fixture['sources'], fixture_excluded, _ = project_sources(fixture['sources'])
        assert not fixture_excluded
        fixture['build_receipt_sha256'] = sha(build)
        save(view / 'byte-fixture.json', fixture)
        generic.create(view, 'tp2', build, view / 'byte-fixture.json',
                       view / 'build/device/own-rt-iq3', view / 'dispatch-speed6.json', view / 'screen-seal.json')
        active = json.loads((view / 'screen-seal.json').read_text())['sources']
        assert all(parent_policy(p) == 'keep' for p in active)
        rows.append(dict(view=label, old_seal_sha256=sha(old / 'screen-seal.json'),
                         new_seal_sha256=sha(view / 'screen-seal.json'),
                         excluded=excluded, snapshots=snapshots,
                         binaries_unchanged=True, selection_unchanged=True))
        print(label, 'resealed without parent orchestration', flush=True)
    save(P / 'evidence/reseal-20261018.json', dict(passed=True, device_executed=False,
         rebuilt=False, old_control_reused=False, views=rows))


if __name__ == '__main__':
    main()
