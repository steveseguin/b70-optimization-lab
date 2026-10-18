#!/usr/bin/env python3
"""Reproduce packet58u's metadata-only bounds; never read weights or devices."""
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
STAGE = HERE.parent.parent
GIB = 1024**3
ROOTS = {
    '58g': 'packet58g-onecard/evidence/card0-58g-a',
    '58k': 'packet58k-onecard-screen/evidence/card0-screen-b',
    '58n': 'packet58n-onecard-loo/evidence/card0-loo-a',
    '58p': 'packet58p-onecard-record/evidence/card0-58p-a',
}
REFUSAL = ('packet58r-onecard-v5/evidence/refused/'
           'card0-v5-a-host-admission-20261018T150354Z/route-rec/WSCREEN/window.json')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def _derive_expanded():
    pins = {}

    def pin(path):
        pins[str(path.relative_to(REPO))] = sha(path)
        return path

    def read(path):
        return json.loads(pin(path).read_text())

    refusal = read(STAGE / REFUSAL)
    base = refusal['memory_admission']['plan']
    file_bytes = base['census']['file_backed_nonexpert_bytes']
    pinned_bytes = base['census']['pinned_expert_bytes']
    lookup = read(STAGE / 'packet58t-resident-lookups/evidence/lookup-inventory.json')
    resident_bytes = lookup['resident_bytes']
    assert resident_bytes == sum(t['bytes'] for t in lookup['tensors']) == 29_321_610_240
    for path, digest in {base['census']['source_path']: base['census']['source_sha256'],
                         **base['allocation_inventory']['sources']}.items():
        assert sha(pin(REPO / path)) == digest
    for rel in ('packet58r-onecard-v5/memory_plan.py', 'packet58r-onecard-v5/window.py',
                'packet58t-resident-lookups/memory_plan.py', 'packet58t-resident-lookups/window.py',
                'packet34-replay-bench/window.py'):
        pin(STAGE / rel)
    windows = []
    for packet, root in ROOTS.items():
        for path in sorted((STAGE / root).rglob('host-memory.jsonl')):
            if 'run' in path.relative_to(STAGE / root).parts:
                continue  # Native snapshots are checked separately, not supervisor samples.
            receipt = read(path.parent / 'window.json')
            assert receipt['passed'] and receipt['device_executed'] and not receipt['stop_reasons']
            admission = receipt['memory_admission']
            budget = admission['plan']
            baseline = admission['baseline_gpuactive_bytes']
            k1 = receipt['window'].startswith('K1')
            view = ('production' if packet == '58g' or 'production-' in str(path)
                    else 'tile16-port-diagnostic' if packet == '58k' else 'tile16')
            # All exactness samples use zero file charge. Normalize them to the
            # same conservative full-file allowance as timing before comparing.
            old_file = (0 if budget.get('admission_mode') == 'census-plus-measured-shadow'
                        else file_bytes)
            peak = normalized_peak = shadow_peak = anon_peak = count = 0
            peak_row = None
            with pin(path).open() as stream:
                for count, line in enumerate(stream, 1):
                    row = json.loads(line)
                    assert 'sensor_error' not in row
                    shadow = max(0, row['host']['GPUActive'] - baseline - row['pinned_expert_bytes'])
                    assert shadow == row['gpuactive_shadow_bytes']
                    assert row['host']['MemAvailable'] >= 8 * GIB
                    shadow_peak = max(shadow_peak, shadow)
                    anon_peak = max(anon_peak, row['anonymous_bytes'])
                    if not k1:
                        actual = row['pinned_expert_bytes'] + shadow + row['anonymous_bytes'] + old_file
                        assert actual == row['host_accounted_bytes']
                        peak = max(peak, actual)
                        normalized = actual - old_file + file_bytes
                        if normalized > normalized_peak:
                            normalized_peak, peak_row = normalized, dict(line=count, sample=row)
            assert count
            native_after_shadow = None
            if not k1:
                post = receipt['postload_memory']
                assert post['complete_postload'] and post['full_cache_bytes'] == 18_000_000_000
                assert post['pinned_expert_bytes'] == pinned_bytes and post['kv_bytes'] == 116_391_936
                for rel, digest in post['sources'].items():
                    assert sha(pin(path.parent / rel)) == digest
                native = read(path.parent / 'run/run/census.json')
                allocations = [a for a in native[0]['allocations'] if a['live']]
                assert len(native) == 1
                assert sum(a['bytes'] for a in allocations if ':pinned-experts:' in a['label']) == pinned_bytes
                assert sum(a['bytes'] for a in allocations if a['label'] == 'card0:immutable-expert-cache') == 18_000_000_000
                assert sum(a['bytes'] for a in allocations if a['category'] == 'KV') == 116_391_936
                assert sum(a['bytes'] for a in allocations if a['memory'] == 'device') <= base['device_owned_bound_bytes']
                native_rows = [json.loads(line) for line in (path.parent / 'run/run/host-memory.jsonl').read_text().splitlines()]
                loaded = [r for r in native_rows if r['phase'] == 'after_load']
                assert len(loaded) == 1
                native_after_shadow = max(0, loaded[0]['GPUActive'] - baseline - pinned_bytes)
                assert native_after_shadow == post['after_load_shadow_bytes']
            windows.append(dict(packet=packet, view=view, window=receipt['window'],
                                source=str(path.relative_to(REPO)), samples=count,
                                full_model=not k1, peak_accounted_bytes=peak,
                                normalized_full_file_peak_bytes=normalized_peak,
                                peak_shadow_bytes=shadow_peak, peak_anonymous_bytes=anon_peak,
                                native_after_load_shadow_bytes=native_after_shadow,
                                peak_witness=peak_row))
    profiles = {}
    for view in ('production', 'tile16'):
        rows = [r for r in windows if r['full_model'] and r['view'] == view]
        maximum = max(r['normalized_full_file_peak_bytes'] for r in rows)
        profiles[view] = dict(measured_view=view, measured_normalized_peak_bytes=maximum,
                              resident_lookup_bytes=0, file_allowance_bytes=file_bytes,
                              empirical_core_peak_bytes=maximum-file_bytes,
                              shadow_bound_bytes=4*GIB, extra_margin_bytes=4*GIB,
                              host_bound_bytes=maximum+4*GIB,
                              host_required_available_bytes=maximum+12*GIB,
                              full_model_windows=len(rows), resident_device_measured=False)
    # The full-file peak ALREADY charges both lookup tensors. Replace their file
    # allowance with anonymous residency, rather than adding the same 29.32 GB
    # twice. Native RssAnon charges the real copies; clean source pages reclaim
    # naturally through MemAvailable, with no advice, warming or cache drops.
    profiles['tile16-resident'] = dict(profiles['tile16'], resident_lookup_bytes=resident_bytes,
                                      file_allowance_bytes=file_bytes-resident_bytes,
                                      design_increment_to_core_bytes=resident_bytes,
                                      replaced_lookup_file_allowance_bytes=resident_bytes,
                                      full_model_windows=0)
    reason = next(r for r in refusal['stop_reasons'] if r.startswith('host admission refused:'))
    available, required, shortage = map(int, re.findall(r'\d+', reason))
    assert required == base['host_required_available_bytes'] and required-available == shortage
    report = dict(schema='own-runtime.packet58u.measured-host-evidence.v1',
                  device_executed=False, windows=windows, profiles=profiles,
                  historical_refusal=dict(source=str((STAGE/REFUSAL).relative_to(REPO)),
                                          started_utc_ns=refusal['started_utc_ns'],
                                          snapshot={'MemAvailable': available},
                                          snapshot_scope='Only MemAvailable was retained in the refusal; no other sensor is invented.',
                                          old_required_bytes=required, old_shortage_bytes=shortage),
                  sources=pins)
    return base, report


def archive_text(path):
    """Read retained metadata from the local archive; no sibling reads."""
    import tarfile
    name=str(Path(path).relative_to(REPO))
    with tarfile.open(HERE.parent/'lineage-inputs/memory-admission-inputs.tar.gz','r:gz') as archive:
        return archive.extractfile(name).read().decode()


def derive():
    """Replay the unchanged arithmetic against a temporary, verified input tree."""
    import tempfile,tarfile
    global REPO,STAGE
    packet=HERE.parent;original_repo,original_stage=REPO,STAGE
    archive_path=packet/'lineage-inputs/memory-admission-inputs.tar.gz'
    expected=json.loads((packet/'lineage-inputs/memory-admission-member-hashes.json').read_text())
    relocations=json.loads((packet/'lineage-inputs/relocated-metadata.json').read_text())
    prefix=str(packet.relative_to(original_repo))+'/lineage-inputs/original/'
    def canonical(name):return name[len(prefix):] if name.startswith(prefix) else name
    def relocated(row):
        if isinstance(row,str):return relocations.get(row,{}).get('local',row)
        if isinstance(row,list):return [relocated(v) for v in row]
        if isinstance(row,dict):return {relocated(k):relocated(v) for k,v in row.items()}
        return row
    with tempfile.TemporaryDirectory(prefix='p58yb-admission-') as tmp:
        with tarfile.open(archive_path,'r:gz') as archive:
            for name,digest in expected.items():
                raw=archive.extractfile(name).read()
                assert hashlib.sha256(raw).hexdigest()==digest,name
                target=Path(tmp)/canonical(name)
                assert target.resolve().is_relative_to(Path(tmp))
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
        try:
            REPO=Path(tmp);STAGE=REPO/'experiments/own-xpu-runtime/stage2'
            base,report=_derive_expanded()
        finally:REPO,STAGE=original_repo,original_stage
    base,report=relocated(base),relocated(report)
    report['sources']={str(archive_path.relative_to(REPO)):sha(archive_path)}
    report['source_policy']='Historical source labels below are archive-member provenance only; no live sibling reads. All original members were verified against their retained hashes.'
    return base,report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    base, report = derive()
    for name, value in [('base-plan.json', base), ('measured-peaks.json', report)]:
        target = HERE / name
        if args.check:
            assert json.loads(target.read_text()) == value, name + ' differs from receipts'
        else:
            target.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'windows': len(report['windows']),
                      'profiles': report['profiles']}, indent=2))
