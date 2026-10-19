"""CPU consistency checks of this packet's real receipts, links and sources."""
import hashlib
import json
import re
from capture import P, ROOT, guard
from analyze import read


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    guard()
    pins=json.loads((P/'evidence/input-pins.json').read_text())
    for name in pins:read(name)
    sources=json.loads((P/'evidence/source-pins.json').read_text())
    for path,digest in sources.items():assert sha(ROOT/path)==digest,path
    cpu=json.loads((P/'evidence/cpu.json').read_text())
    assert cpu['passed'] and len(cpu['records'])==4
    assert len({r['output_sha256'] for r in cpu['records']})==1
    assert len({r['pid'] for r in cpu['records']})==4
    for mode in ('gnu','intel'):
        build=json.loads((P/f'evidence/build-{mode}.json').read_text())
        for path,digest in build['sources'].items():assert sha(ROOT/path)==digest,path
        assert build['device_executed'] is False
        for repeat in (1,2):
            r=json.loads((P/f'evidence/cpu-{mode}-{repeat}.json').read_text())
            assert r['passed'] and not r['device_executed'] and r['cases']==2304
            assert r['nonfinite']==256 and r['invalid_abi']==18 and r['invalid_selected_routes']==5
            assert sha(P/f'build/{mode}-{repeat}.bytes')==r['output_sha256']
            assert sha(P/f'build/gate-{mode}')==r['binary_sha256']==build['binary_sha256']
    links=0
    for path in [*P.rglob('*.md'),ROOT/'notes/2026-10-19-own-runtime-packet164.md']:
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if target.startswith(('http:','https:','#')):continue
            assert (path.parent/target.split('#')[0]).exists(),(path,target)
            links+=1
    rows=[json.loads(line) for line in (P/'briefs/lanequeue-rows.jsonl').read_text().splitlines()]
    assert len(rows)==2 and len({r['name'] for r in rows})==2
    for r in rows:
        assert r['lane']=='A' and r['planned_write_bytes']>0 and '--authorized-device-window' in r['argv']
        assert not (ROOT/r['argv'][2]).exists() # documentary, deliberately unbuilt
        assert not r['plan']['entry_rehearsal'].get('binaries')
        assert '{REVIEW}' in r['argv']
    assert not list(P.glob('*READY*'))
    files=[p for p in P.rglob('*') if p.is_file() and 'build' not in p.relative_to(P).parts and '__pycache__' not in p.relative_to(P).parts]
    assert max(p.stat().st_size for p in files)<1024**2
    out=dict(passed=True,input_files=len(pins),pinned_decision_sources=len(sources),links=links,
             retained_files=len(files),largest_file_bytes=max(p.stat().st_size for p in files),
             bytes_total=sum(p.stat().st_size for p in files),device_executed=False,ready_written=False,
             actual_queue_rehearsal_performed=False,queue_rows_are_documentary=True)
    (P/'evidence/validation.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(out))


if __name__=='__main__':main()
