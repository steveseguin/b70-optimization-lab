#!/usr/bin/env python3
"""Retain ring evidence without duplicating byte-identical durable portable state."""
import argparse
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import tarfile

from archive_live_proofs import stream_hash
from finalize_wavefront_proof import HERE, compare, identity
from restore_reused_state import Archive, digest_stream, members, restore


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True,type=Path);p.add_argument('--receipt',required=True,type=Path)
    p.add_argument('--restore-check',required=True,type=Path)
    a=p.parse_args()
    full=json.loads((HERE/'ring-scripted-archive-verification.json').read_text())
    portable=json.loads((HERE/'portable-live-archive-verification.json').read_text())
    durable=json.loads((HERE/'portable-live-durable-archive.json').read_text())
    summary=json.loads((HERE/'ring-scripted-proof/summary.json').read_text())
    assert full['passed'] and portable['passed'] and summary['passed']
    assert durable['durable'] and durable['copied_content_independently_rehashed']
    assert (durable['bytes'],durable['sha256'])==(portable['archive']['bytes'],portable['archive']['sha256'])
    run=Path(summary['source_run']);rows=[];expected={}
    for stage in range(4):
        suffix=f'stage{stage}/native/state-2147483647/state.bundle'
        dest=f'{run.name}/{suffix}';source_member='pp4/'+suffix
        old=next(r for r in portable['raw_state_members'] if r['member']==source_member)
        current=next(r for r in full['raw_state_members'] if r['member']==dest)
        assert (old['bytes'],old['sha256'])==(current['bytes'],current['sha256'])
        raw=run/suffix;seal=raw.with_name('state-seal.txt').read_text().splitlines()
        metadata={name:identity(raw.with_name(name))['sha256'] for name in ('state-seal.txt','state-index.tsv','state.json')}
        assert metadata['state-index.tsv']==seal[3] and metadata['state.json']==seal[4]
        old_seal=Path(old['source_seal']['path']).read_text().splitlines()
        assert old_seal==seal and metadata['state-seal.txt']==old['source_seal']['sha256']
        row=dict(original_path=str(raw),archive_path=dest,source_member=source_member,
            bytes=current['bytes'],sha256=current['sha256'],metadata_sha256=metadata,
            source_archive_path=durable['path'],source_archive_sha256=durable['sha256'])
        rows.append(row);expected[dest]=(row['bytes'],row['sha256'])
    manifest=dict(schema='ownrt.reused-state-archive.v1',source_archive=durable,bundles=rows,
        full_raw_bytes=sum(r['bytes'] for r in rows),new_raw_bytes=0,
        complete_tmpfs_archive=full['archive'],
        scope='Every raw state payload, native seal, index and state JSON is identical to the named previously durable portable-live member. New native ring layouts, attestations, traces, code and comparisons remain in this metadata archive.',
        restore='Run restore_reused_state.py --metadata-archive THIS_ARCHIVE --metadata-sha256 HASH_FROM_EXTERNAL_RECEIPT --raw-archive SOURCE_ARCHIVE --out FRESH_DIRECTORY. Creates independently hashed single-link files; no originals deleted.')
    manifest_raw=(json.dumps(manifest,indent=2)+'\n').encode()
    full_file=Archive(full['archive']['path'],full['archive']['sha256'],full['archive']['bytes'])
    seen=set();kept={}
    try:
        with tarfile.open(fileobj=full_file.stream,mode='r|gz') as incoming,tarfile.open(a.archive,'x:gz',compresslevel=1) as outgoing:
            for member in members(incoming,2*1024**3):
                if member.name in expected:
                    assert member.isfile()
                    with incoming.extractfile(member) as source:assert digest_stream(source)==expected[member.name]
                    seen.add(member.name);continue
                assert Path(member.name).name!='state.bundle','unmapped raw bundle cannot be omitted'
                if member.isfile():
                    raw=incoming.extractfile(member).read();assert len(raw)==member.size
                    import hashlib
                    kept[member.name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                    outgoing.addfile(member,io.BytesIO(raw))
                else:outgoing.addfile(member)
            for name,raw in [('reused-state-map.json',manifest_raw)]+[(n,(HERE/n).read_bytes()) for n in
                ('restore_reused_state.py','test_restore_reused_state.py','archive_ring_reuse.py')]:
                assert name not in kept
                import hashlib
                kept[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
                member=tarfile.TarInfo(name);member.mode=0o600;member.size=len(raw);outgoing.addfile(member,io.BytesIO(raw))
        full_file.check()
    finally:full_file.close()
    assert seen==set(expected)
    with a.archive.open('rb') as source:size,sha=stream_hash(source)
    observed={}
    with tarfile.open(a.archive,'r|gz') as archive:
        for member in members(archive,128*1024**2):
            if not member.isfile():continue
            with archive.extractfile(member) as source:n,h=stream_hash(source)
            observed[member.name]=dict(bytes=n,sha256=h)
    assert observed==kept,'metadata archive content/hash inventory differs'
    restored=restore(a.archive,sha,Path(durable['path']),a.restore_check)
    checked=[]
    for row in rows:
        bundle=a.restore_check/row['archive_path'];hashes=compare.BUNDLE.read_state(bundle.parent)
        assert bundle.stat().st_nlink==1
        checked.append(dict(path=str(bundle),bytes=bundle.stat().st_size,sha256=row['sha256'],
                            native_sealed_reader_passed=True,buffer_hash_count=len(hashes)))
    receipt=dict(schema='ownrt.ring-reuse-archive-verification.v1',passed=True,
        verified_utc=datetime.now(timezone.utc).isoformat(),archive=dict(path=str(a.archive.resolve()),bytes=size,sha256=sha,durable=False),
        source_durable_archive=durable,manifest=manifest,regular_members=len(kept),member_inventory=kept,
        restoration_check=restored,restored_sealed_bundles=checked,
        full_tmpfs_archive_preserved=full['archive'],originals_preserved=True,script=identity(Path(__file__)),
        method='Complete archive raw hashes verified against native seals; metadata member inventory independently rehashed; durable source archive authenticated and each referenced raw/seal/index/state member verified while making independent copies; every restored bundle passed the strict native state reader.')
    with a.receipt.open('x') as output:json.dump(receipt,output,indent=2);output.write('\n')
    print(json.dumps({k:receipt[k] for k in ('passed','archive','regular_members','restoration_check')}))


if __name__=='__main__':main()
