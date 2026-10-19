"""Finalize a CPU study receipt; never qualify a runtime or device launch."""
import hashlib
import json
from pathlib import Path
import re
import resource
import shutil
import subprocess

from audit import guard, P, ROOT


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    guard()
    pins=json.loads((P/'evidence/input-pins.json').read_text())
    pins.update(json.loads((P/'evidence/scope-report.json').read_text())['input_pins'])
    for name,pin in pins.items():
        path=ROOT/name
        assert digest(path)==pin['sha256'] and path.stat().st_size==pin['bytes'], name
    tracked=set(subprocess.check_output(['git','ls-files'],cwd=ROOT,text=True).splitlines())
    external=[name for name in pins if not name.startswith(str(P.relative_to(ROOT))+'/')]
    assert all(name in tracked for name in external), 'untracked external replay dependency'
    audit=json.loads((P/'evidence/prior-audit.json').read_text())
    changed=[r['path'] for r in audit['files'] if digest(ROOT/r['path'])!=r['sha256']]
    reviewed=json.loads((P/'evidence/prior-audit-updates.json').read_text())
    assert set(changed)==set(reviewed), f'unreviewed negative-result changes: {changed}'
    for name,entry in reviewed.items():
        assert digest(ROOT/name)==entry['reviewed_sha256'], f'audit changed again: {name}'
        assert next(r['sha256'] for r in audit['files'] if r['path']==name)==entry['entry_sha256']
    source_paths=[
        'experiments/own-xpu-runtime/stage2/packet136-record-bundle/native_controller.hpp',
        'experiments/own-xpu-runtime/stage2/packet136-record-bundle/rank.hpp',
        'experiments/own-xpu-runtime/stage2/packet106-draft-split/DESIGN.md',
        'experiments/own-xpu-runtime/stage2/packet149-shared-correction-probe/v5/native/probe_exchange.hpp',
        'experiments/own-xpu-runtime/stage2/packet156-draft-slack/evidence/bracket-bound.json',
        'experiments/own-xpu-runtime/stage2/packet158-draft-levers/ROOFLINE.md',
        'experiments/own-xpu-runtime/stage2/packet158-draft-levers/SOURCE-MAP.md',
        'notes/2026-10-17-own-runtime-packet71c.md',
        'notes/2026-10-18-own-runtime-packet106b-grid-result.md',
        'notes/2026-10-18-own-runtime-packet120-grid-result.md',
        'notes/2026-10-18-own-runtime-packet145-result.md',
        'notes/2026-10-18-own-runtime-packet149-result.md',
        'notes/2026-10-19-own-runtime-packet150-result.md',
        'notes/2026-10-19-own-runtime-packet153-result.md',
        'notes/2026-10-19-own-runtime-packet154-result.md',
        'notes/2026-10-19-own-runtime-draft-line-closure.md',
    ]
    source_pins={name:dict(sha256=digest(ROOT/name),bytes=(ROOT/name).stat().st_size) for name in source_paths}
    (P/'evidence/source-pins.json').write_text(json.dumps(source_pins,indent=2)+'\n')
    note=ROOT/'notes/2026-10-19-own-runtime-packet160.md'
    links=0
    for path in [*P.glob('*.md'),note]:
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if target.startswith(('http:','https:','#')):continue
            assert (path.parent/target.split('#')[0]).exists(), (path,target)
            links+=1
    assert not list(P.glob('READY*')) and not (P/'proposals').exists() and not (P/'briefs').exists()
    replay=json.loads((P/'evidence/replay-check.json').read_text())
    assert replay['passed'] and replay['check']
    scoped=json.loads((P/'evidence/scopes-check.json').read_text())
    assert scoped['passed'] and scoped['intervals']==3780
    tests=(P/'evidence/tests.log').read_text()
    assert 'Ran 18 tests' in tests and tests.rstrip().endswith('OK')
    files=[p for p in P.rglob('*') if p.is_file()]
    large=[p for p in files if p.stat().st_size>=1024**2]
    assert large==[P/'evidence/scoped-intervals.csv.gz'], 'unexpected large artifact'
    assert f'{large[0].stat().st_size:,}' in (P/'RETENTION.md').read_text(), 'large artifact rationale required'
    assert not list(P.rglob('__pycache__'))
    report=dict(schema='packet160.cpu-study-validation.v1',passed=True,
        device_ready=False,build_briefs_admitted=0,proposals=0,
        record_intervals=1188,real_parent_scope_intervals=3780,tests=18,
        pinned_replay_files=len(pins),tracked_external_replay_files=len(external),
        negative_indexes_rechecked=len(audit['files']),negative_indexes_changed=changed,
        local_links_checked=links,retained_bytes_before_this_receipt=sum(p.stat().st_size for p in files),
        largest_artifact_bytes=max(p.stat().st_size for p in files),root_free_bytes=shutil.disk_usage(ROOT).free,
        retention_review='RETENTION.md: full original-precision per-interval scope table',
        cpu_stop_root_free_bytes=27_000_000_000,device_floor_root_free_bytes=25_000_000_000,
        planned_build_bytes=0,planned_device_writes=0,
        peak_scope_replay_rss_kib=scoped['peak_rss_kib'],peak_record_replay_rss_kib=replay['peak_rss_kib'],
        final_source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        method_hashes={p.name:digest(p) for p in P.glob('*.py')})
    (P/'evidence/validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':main()
