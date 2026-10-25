#!/usr/bin/env python3
"""Archive completed live proofs; independently stream-check every raw bundle."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import tarfile

from finalize_wavefront_proof import HERE, OWNRT, compare, identity, save


def stream_hash(stream):
    value=hashlib.sha256();size=0
    while chunk:=stream.read(1024*1024):value.update(chunk);size+=len(chunk)
    return size,value.hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',required=True,type=Path)
    parser.add_argument('--receipt',required=True,type=Path)
    args=parser.parse_args()
    expected={}
    runs=[]
    for name in ('live-pp2-proof-v2','live-pp4-proof'):
        summary=json.loads((HERE/name/'summary.json').read_text())
        assert summary['passed'] is True
        run=Path(summary['source_run']);runs.append(run)
        terminal=json.loads((run/'result.json').read_text())
        assert terminal['passed'] is True and terminal['live_pids']==[]
        for dump in run.rglob('state.bundle'):
            compare.BUNDLE.read_state(dump.parent)
            seal=(dump.parent/'state-seal.txt').read_text().splitlines()
            member=str(Path(run.name)/dump.relative_to(run))
            expected[member]=dict(bytes=int(seal[1]),sha256=seal[2],
                source_seal=identity(dump.parent/'state-seal.txt'))
    sources=[(run,run.name) for run in runs]
    for name in ('live-pp2-proof','live-pp2-proof-v2','live-pp4-proof','live-mtp-review.md',
                 'live-draft-legacy-prefix.json','finalize_live_proof.py','archive_live_proofs.py',
                 'finalize_wavefront_proof.py'):
        sources.append((HERE/name,'proof/'+name))
    for path in (OWNRT/'engine/tools/compare_pipeline_state.py',OWNRT/'engine/tools/compare_draft_state.py',
                 OWNRT/'gsq-rco-iq3s/state-bundle/reader.py'):
        sources.append((path,'source/'+str(path.relative_to(OWNRT))))
    def checked(member):
        assert member.isfile() or member.isdir(), 'only regular evidence files/directories may be archived'
        return member
    with tarfile.open(args.archive,'x:gz',compresslevel=1) as archive:
        for source,name in sources:archive.add(source,arcname=name,filter=checked)
    with args.archive.open('rb') as stream:archive_size,archive_sha=stream_hash(stream)
    seen=set();members=0;verified=[]
    with tarfile.open(args.archive,'r|gz') as archive:
        for member in archive:
            if member.isfile():members+=1
            if member.name not in expected:continue
            assert member.isfile() and member.name not in seen
            with archive.extractfile(member) as stream:size,sha=stream_hash(stream)
            want=expected[member.name]
            assert size==member.size==want['bytes'] and sha==want['sha256']
            seen.add(member.name);verified.append(dict(member=member.name,bytes=size,sha256=sha,
                source_seal=want['source_seal'],passed=True))
    assert seen==set(expected)
    receipt=dict(schema='ownrt.live-proof-archive-verification.v1',passed=True,
        verified_utc=datetime.now(timezone.utc).isoformat(),archive=dict(path=str(args.archive.resolve()),
        bytes=archive_size,sha256=archive_sha,durable=False),archive_members=members,
        raw_state_members=verified,raw_state_bytes=sum(x['bytes'] for x in verified),
        method='Native sealed reader first; separate completed archive SHA256 pass; independent streaming tar raw-member SHA256 pass against source seals. No originals removed.',
        scope='Both terminally clean runs, target/draft raw state, passed proof packets, first refused audit, exact comparison scripts.',
        script=identity(Path(__file__)))
    with args.receipt.open('x') as out:json.dump(receipt,out,indent=2);out.write('\n')
    print(json.dumps({k:receipt[k] for k in ('passed','archive','archive_members','raw_state_bytes')}))


if __name__=='__main__':main()
