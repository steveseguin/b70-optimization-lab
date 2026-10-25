#!/usr/bin/env python3
"""Deduplicate raw state by authenticated SHA256 while preserving every path/seal."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile

from archive_live_proofs import stream_hash
from finalize_wavefront_proof import HERE, OWNRT, compare, identity


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--proof',required=True,type=Path)
    p.add_argument('--archive',required=True,type=Path)
    p.add_argument('--receipt',required=True,type=Path)
    a=p.parse_args();proof=a.proof.resolve()
    summary=json.loads((proof/'summary.json').read_text());assert summary['passed'] is True
    run=Path(summary['source_run']);result=json.loads((run/'result.json').read_text())
    assert result['passed'] is True and result['live_pids']==[]
    bundles=[];unique={}
    for raw in sorted(run.rglob('state.bundle')):
        compare.BUNDLE.read_state(raw.parent)
        seal=(raw.parent/'state-seal.txt').read_text().splitlines();size,sha=int(seal[1]),seal[2]
        bundles.append(dict(original_path=str(raw),archive_path='run/'+str(raw.relative_to(run)),
            blob='blobs/sha256/'+sha,bytes=size,sha256=sha,source_seal=identity(raw.parent/'state-seal.txt')))
        if sha in unique:assert unique[sha]['bytes']==size
        else:unique[sha]=dict(path=raw,bytes=size)
    mapping=dict(schema='ownrt.state-bundle-cas.v1',bundles=bundles,
        restore='After extracting, run python3 restore_state_bundles.py --root EXTRACTED_DIRECTORY. Makes independent copies; no hardlinks.',
        full_raw_bytes=sum(r['bytes'] for r in bundles),unique_raw_bytes=sum(r['bytes'] for r in unique.values()))
    mapping_raw=(json.dumps(mapping,indent=2)+'\n').encode()
    sources=[(run,'run'),(proof,'proof')]
    for name in ('finalize_persistent_proof.py','finalize_live_proof.py','finalize_wavefront_proof.py',
                 'archive_persistent_proof.py','archive_live_proofs.py'):
        sources.append((HERE/name,'source/'+name))
    for path in (OWNRT/'engine/tools/compare_pipeline_state.py',OWNRT/'engine/tools/compare_draft_state.py',
                 OWNRT/'gsq-rco-iq3s/state-bundle/reader.py'):
        sources.append((path,'source/'+str(path.relative_to(OWNRT))))
    sources.append((HERE/'restore_state_bundles.py','restore_state_bundles.py'))
    def checked(member):
        assert member.isfile() or member.isdir(),'regular evidence files only'
        return None if Path(member.name).name=='state.bundle' else member
    with tarfile.open(a.archive,'x:gz',compresslevel=1) as archive:
        for path,name in sources:archive.add(path,arcname=name,filter=checked)
        for sha,row in sorted(unique.items()):archive.add(row['path'],arcname='blobs/sha256/'+sha)
        member=tarfile.TarInfo('state-bundle-map.json');member.size=len(mapping_raw);member.mode=0o600
        archive.addfile(member,io.BytesIO(mapping_raw))
    with a.archive.open('rb') as stream:size,sha=stream_hash(stream)
    seen=set();members=0;mapping_checked=False
    with tarfile.open(a.archive,'r|gz') as archive:
        for member in archive:
            if member.isfile():members+=1
            if member.name=='state-bundle-map.json':
                assert archive.extractfile(member).read()==mapping_raw;mapping_checked=True
            if not member.name.startswith('blobs/sha256/'):continue
            key=member.name.removeprefix('blobs/sha256/');assert key in unique and key not in seen
            with archive.extractfile(member) as stream:observed_size,observed_sha=stream_hash(stream)
            assert observed_size==member.size==unique[key]['bytes'] and observed_sha==key
            seen.add(key)
    assert seen==set(unique) and mapping_checked
    receipt=dict(schema='ownrt.persistent-proof-archive-verification.v1',passed=True,
        verified_utc=datetime.now(timezone.utc).isoformat(),archive=dict(path=str(a.archive.resolve()),
        bytes=size,sha256=sha,durable=False),regular_members=members,bundle_count=len(bundles),unique_blobs=len(unique),
        full_raw_bytes=mapping['full_raw_bytes'],unique_raw_bytes=mapping['unique_raw_bytes'],mapping=mapping,
        method='Every original sealed bundle authenticated; separate compressed archive SHA256 pass; independent tar blob hash pass; exact mapping round-trip. Originals preserved.',
        script=identity(Path(__file__)))
    with a.receipt.open('x') as output:json.dump(receipt,output,indent=2);output.write('\n')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('mapping','script','method')}))


if __name__=='__main__':main()
