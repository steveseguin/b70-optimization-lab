#!/usr/bin/env python3
"""Archive a completed cold suite or portable-live proof, checking sealed raw members."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import tarfile

from archive_live_proofs import stream_hash
from finalize_wavefront_proof import HERE, OWNRT, compare, identity


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for key in ('run','proof','archive','receipt'):
        parser.add_argument('--'+key,type=Path,required=True)
    args=parser.parse_args()
    run,proof=args.run.resolve(),args.proof.resolve()
    terminal=json.loads((run/'result.json').read_text())
    summary=json.loads((proof/'summary.json').read_text())
    assert terminal['passed'] is True and terminal['live_pids']==[] and all(v==0 for v in terminal['returncodes'].values())
    assert summary['passed'] is True
    suite=summary['schema']=='ownrt.persistent-suite-audit.v1' and summary['requests']==12
    portable=summary['schema']=='ownrt.portable-live-proof.v1' and summary['source_run']==str(run)
    assert suite or portable,'supported passed suite or portable-live proof required'
    expected={}
    for bundle in sorted(run.rglob('state.bundle')):
        compare.BUNDLE.read_state(bundle.parent)
        seal=(bundle.parent/'state-seal.txt').read_text().splitlines()
        expected[str(Path(run.name)/bundle.relative_to(run))]=dict(bytes=int(seal[1]),sha256=seal[2],
            source_seal=identity(bundle.parent/'state-seal.txt'))
    assert len(expected)==6,'expected four terminal target and two terminal draft bundles'
    sources=[(run,run.name),(proof,'proof/'+proof.name)]
    for name in ('archive_completed_suite.py','archive_live_proofs.py','audit_persistent_suite.py',
                 'finalize_persistent_proof.py','finalize_live_proof.py','finalize_wavefront_proof.py',
                 'test_audit_persistent_suite.py'):
        sources.append((HERE/name,'proof/'+name))
    if portable:
        for name in ('finalize_portable_live_proof.py','test_finalize_portable_live_proof.py','finalize_portable_proof.py',
                     'live-draft-legacy-prefix.json'):
            sources.append((HERE/name,'proof/'+name))
    for path in (OWNRT/'engine/tools/compare_pipeline_state.py',OWNRT/'engine/tools/compare_draft_state.py',
                 OWNRT/'gsq-rco-iq3s/state-bundle/reader.py'):
        sources.append((path,'source/'+str(path.relative_to(OWNRT))))
    def regular(member):
        assert member.isfile() or member.isdir(),'only regular evidence accepted'
        return member
    with tarfile.open(args.archive,'x:gz',compresslevel=1) as archive:
        for path,name in sources:archive.add(path,arcname=name,filter=regular)
    with args.archive.open('rb') as stream:size,sha=stream_hash(stream)
    seen=set();verified=[];count=0
    with tarfile.open(args.archive,'r|gz') as archive:
        for member in archive:
            if member.isfile():count+=1
            if member.name not in expected:continue
            assert member.isfile() and member.name not in seen
            with archive.extractfile(member) as stream:n,digest=stream_hash(stream)
            want=expected[member.name]
            assert n==member.size==want['bytes'] and digest==want['sha256']
            verified.append(dict(member=member.name,bytes=n,sha256=digest,source_seal=want['source_seal'],passed=True))
            seen.add(member.name)
    assert seen==set(expected)
    receipt=dict(schema='ownrt.completed-suite-archive-verification.v1',passed=True,
        verified_utc=datetime.now(timezone.utc).isoformat(),archive=dict(path=str(args.archive.resolve()),bytes=size,sha256=sha,durable=False),
        archive_members=count,raw_state_members=verified,raw_state_bytes=sum(r['bytes'] for r in verified),
        script=identity(Path(__file__)),method='Native sealed reader, completed archive SHA256, then independent streaming member hashes against native seals.',
        scope='All completed run controller/native logs and final target/draft raw state plus compact audit. Original files remain untouched.')
    with args.receipt.open('x') as stream:json.dump(receipt,stream,indent=2);stream.write('\n')
    print(json.dumps({k:receipt[k] for k in ('passed','archive','archive_members','raw_state_bytes')}))


if __name__=='__main__':main()
