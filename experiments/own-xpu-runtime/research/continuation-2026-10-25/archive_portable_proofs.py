#!/usr/bin/env python3
"""Retain completed portable target replays and verify archived raw state."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tarfile

from archive_live_proofs import stream_hash
from finalize_wavefront_proof import HERE, OWNRT, compare, identity


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    a=p.parse_args()
    sources=[];expected={}
    for name in ('pp2','pp4'):
        summary=json.loads((HERE/'portable'/f'{name}-proof'/'summary.json').read_text())
        assert summary['passed'] is True
        run=Path(summary['source_run']);terminal=json.loads((run/'result.json').read_text())
        assert terminal['passed'] is True and terminal['live_pids']==[]
        arc='portable-'+name;sources.append((run,arc))
        for bundle in run.rglob('state.bundle'):
            compare.BUNDLE.read_state(bundle.parent)
            seal=(bundle.parent/'state-seal.txt').read_text().splitlines()
            expected[str(Path(arc)/bundle.relative_to(run))]=dict(bytes=int(seal[1]),sha256=seal[2],
                source_seal=identity(bundle.parent/'state-seal.txt'))
    sources.append((HERE/'portable','proof/portable'))
    for name in ('finalize_portable_proof.py','finalize_live_proof.py','finalize_wavefront_proof.py',
                 'archive_portable_proofs.py','archive_live_proofs.py'):
        sources.append((HERE/name,'proof/'+name))
    for path in (OWNRT/'engine/tools/compare_pipeline_state.py',OWNRT/'engine/tools/compare_draft_state.py',
                 OWNRT/'gsq-rco-iq3s/state-bundle/reader.py'):
        sources.append((path,'source/'+str(path.relative_to(OWNRT))))
    def regular(member):
        assert member.isfile() or member.isdir(),'archive must contain only regular evidence'
        return member
    with tarfile.open(a.archive,'x:gz',compresslevel=1) as archive:
        for path,name in sources:archive.add(path,arcname=name,filter=regular)
    with a.archive.open('rb') as stream:size,sha=stream_hash(stream)
    verified=[];seen=set();members=0
    with tarfile.open(a.archive,'r|gz') as archive:
        for member in archive:
            if member.isfile():members+=1
            if member.name not in expected:continue
            assert member.isfile() and member.name not in seen
            with archive.extractfile(member) as stream:count,observed=stream_hash(stream)
            want=expected[member.name]
            assert count==member.size==want['bytes'] and observed==want['sha256']
            seen.add(member.name);verified.append(dict(member=member.name,bytes=count,sha256=observed,
                source_seal=want['source_seal'],passed=True))
    assert seen==set(expected)
    receipt=dict(schema='ownrt.portable-proof-archive-verification.v1',passed=True,
        verified_utc=datetime.now(timezone.utc).isoformat(),archive=dict(path=str(a.archive.resolve()),
        bytes=size,sha256=sha,durable=False),archive_members=members,raw_state_members=verified,
        raw_state_bytes=sum(x['bytes'] for x in verified),script=identity(Path(__file__)),
        method='Native sealed reader; separate archive SHA256 pass; independent streaming tar member check against native seals.',
        scope='Completed portable target-only two/four stage runs and retained authentication/build/proof metadata. Original raw files preserved.')
    with a.receipt.open('x') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
    print(json.dumps({k:receipt[k] for k in ('passed','archive','archive_members','raw_state_bytes')}))


if __name__=='__main__':main()
