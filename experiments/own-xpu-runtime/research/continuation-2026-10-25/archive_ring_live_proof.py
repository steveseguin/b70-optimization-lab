#!/usr/bin/env python3
"""Explicit PASSED live-ring full archive and optional exact durable-byte reuse.

Commands never run engines or delete original evidence. Reuse requires raw bytes
AND all three native metadata hashes to match. Every mismatch remains embedded.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

from finalize_wavefront_proof import HERE, OWNRT, compare, identity
from restore_reused_state import Archive, digest_stream, members, need
from restore_ring_live_archive import META, MAP, restore


def read(path):return json.loads(Path(path).read_text())
def save(path,value):
    with Path(path).open('x') as out:json.dump(value,out,indent=2);out.write('\n')


def archive_identity(path):
    with Path(path).open('rb') as stream:size,sha=digest_stream(stream)
    return dict(path=str(Path(path).resolve()),bytes=size,sha256=sha,durable=False)


def inventory(path):
    result={}
    with tarfile.open(path,'r|gz') as archive:
        for member in members(archive,4*1024**3):
            if member.isfile():
                with archive.extractfile(member) as stream:size,sha=digest_stream(stream)
                need(size==member.size,'archive member truncated');result[member.name]=dict(bytes=size,sha256=sha)
    return result


def full(run,proof,archive_path,receipt_path):
    run,proof=Path(run).resolve(),Path(proof).resolve();summary=read(proof/'summary.json');terminal=read(run/'ring-live-result.json')
    need(summary.get('schema')=='ownrt.ring-live-proof.v1' and summary.get('passed') is True
         and summary.get('source_run')==str(run) and summary.get('target_state_exact') is True
         and summary.get('draft_state_exact') is True,'PASSED explicit target/draft live-ring proof required')
    plan=read(run/'plan.json')
    need(terminal.get('schema')=='ownrt.ring-live-driver-result.v1' and terminal.get('passed') is True
         and terminal.get('live_pids')==[] and terminal.get('returncodes')=={str(s['id']):0 for s in plan['stages']}
         and terminal['plan_sha256']==identity(run/'plan.json')['sha256']
         and terminal['lifecycle_result_sha256']==identity(run/'result.json')['sha256'],'clean hash-bound terminal live-ring result required')
    qualified={str(Path(r['path']).resolve()):(r['bytes'],r['sha256']) for r in summary['raw_bundles']}
    need(len(qualified)==len(plan['stages'])+1,'expected one qualified target per stage plus canonical draft')
    raw=[];observed=set()
    for bundle in sorted(run.rglob('state.bundle')):
        need(not bundle.is_symlink(),'raw symlink refused');compare.BUNDLE.read_state(bundle.parent)
        seal=(bundle.parent/'state-seal.txt').read_text().splitlines();key=str(bundle.resolve());observed.add(key)
        if key in qualified:need(qualified[key]==(int(seal[1]),seal[2]),'qualified raw seal changed')
        raw.append(dict(original_path=key,archive_path=str(Path(run.name)/bundle.relative_to(run)),bytes=int(seal[1]),sha256=seal[2],
                        qualified=key in qualified,metadata_sha256={n:identity(bundle.parent/n)['sha256'] for n in META}))
    need(set(qualified)<=observed,'qualified raw state missing')
    need(len(raw)<=len(plan['stages'])+2,'unexpected raw bundle inventory requires review')
    # FINISH currently emits an additional sealed draft. Preserve it even if it
    # differs; do not quietly promote it to the independently qualified DUMP.
    for row in raw:
        if not row['qualified']:need(Path(row['original_path']).parent.name=='draft-final-state-sealed','unregistered additional raw bundle')
    config=Path(plan['config']);config_data=read(config);build_receipt=Path(config_data['build_receipt'])
    sources=[(run,run.name),(proof,'proof/'+proof.name),(config,'proof/run-config.json'),(build_receipt,'proof/build-receipt.json')]
    for name in ('archive_ring_live_proof.py','restore_ring_live_archive.py','restore_reused_state.py',
                 'test_archive_ring_live_proof.py','finalize_ring_live_proof.py','test_finalize_ring_live_proof.py',
                 'finalize_ring_proof.py','finalize_live_proof.py','finalize_wavefront_proof.py','live-draft-legacy-prefix.json'):
        sources.append((HERE/name,'proof/'+name))
    for relative in ('engine/src/pipeline/recursive_provider','engine/src/pipeline/ring','engine/src/pipeline/operator_state.hpp',
                     'engine/src/pipeline/checkpoint.hpp','engine/src/gsq-rco-iq3s/dense-packed-block/engine/build/source/main.cpp',
                     'engine/src/gsq-rco-iq3s/state-bundle/build/source-v4/rank.hpp',
                     'engine/src/gsq-rco-iq3s/integration/build/private/source/diet-native/native-src/mtp.hpp',
                     'engine/tools/ring_live_driver.py','engine/tools/ring_live_wire.py',
                     'engine/tools/test_ring_live_driver.py','engine/tools/test_ring_live_wire.py',
                     'engine/tools/compare_pipeline_state.py','engine/tools/compare_draft_state.py',
                     'engine/tools/test_compare_ring_live_state.py','gsq-rco-iq3s/state-bundle/reader.py'):
        sources.append((OWNRT/relative,'source/'+relative))
    def regular(member):
        need(member.isfile() or member.isdir(),'only regular evidence files/directories permitted');return member
    with tarfile.open(archive_path,'x:gz',compresslevel=1) as archive:
        for path,name in sources:archive.add(path,arcname=name,filter=regular)
    contents=inventory(archive_path)
    need({name for name in contents if PurePosixPath(name).name=='state.bundle'}=={r['archive_path'] for r in raw},'archive raw inventory differs')
    for row in raw:
        need(contents[row['archive_path']]==dict(bytes=row['bytes'],sha256=row['sha256']),'archived raw differs from sealed source')
        for name,sha in row['metadata_sha256'].items():need(contents[str(PurePosixPath(row['archive_path']).parent/name)]['sha256']==sha,'archived metadata differs')
    result=dict(schema='ownrt.ring-live-full-archive.v1',passed=True,archive=archive_identity(archive_path),bundles=raw,
        proof_summary=identity(proof/'summary.json'),regular_members=len(contents),member_inventory=contents,
        raw_bytes=sum(r['bytes'] for r in raw),qualified_bundles=len(qualified),originals_preserved=True,
        script=identity(Path(__file__)),verified_utc=datetime.now(timezone.utc).isoformat())
    save(receipt_path,result);return result


def source_catalog(receipt):
    need(receipt['durable'] is True and receipt['copied_content_independently_rehashed'] is True,'authenticated durable source required')
    held=Archive(receipt['path'],receipt['sha256'],receipt['bytes']);groups={}
    try:
        with tarfile.open(fileobj=held.stream,mode='r|gz') as archive:
            for member in members(archive,4*1024**3):
                path=PurePosixPath(member.name)
                if not member.isfile() or path.name not in (*META,'state.bundle'):continue
                with archive.extractfile(member) as stream:observed=digest_stream(stream)
                need(observed[0]==member.size,'source member truncated');groups.setdefault(str(path.parent),{})[path.name]=observed
        held.check()
    finally:held.close()
    return [dict(source_member=parent+'/state.bundle',bytes=group['state.bundle'][0],sha256=group['state.bundle'][1],
                 metadata_sha256={n:group[n][1] for n in META}) for parent,group in groups.items() if set(group)==set(META)|{'state.bundle'}]


def choose_storage(rows,catalog):
    result=[]
    for original in rows:
        row=dict(original)
        match=next((r for r in catalog if all(r[k]==row[k] for k in ('bytes','sha256','metadata_sha256'))),None)
        row['storage']='reuse' if match else 'embedded'
        if match:row['source_member']=match['source_member']
        result.append(row)
    return result


def reuse(full_receipt,source_receipt,archive_path,receipt_path,restore_check):
    complete=read(full_receipt)
    need(complete['schema']=='ownrt.ring-live-full-archive.v1' and complete['passed'] is True,'verified complete live-ring archive required')
    source=read(source_receipt) if source_receipt else None
    rows=choose_storage(complete['bundles'],source_catalog(source) if source else [])
    manifest=dict(schema='ownrt.ring-live-reuse-archive.v1',source_archive=source,bundles=rows,
        complete_archive=complete['archive'],new_raw_bytes=sum(r['bytes'] for r in rows if r['storage']=='embedded'),
        reused_raw_bytes=sum(r['bytes'] for r in rows if r['storage']=='reuse'),
        scope='Reused bytes require exact raw/seal/index/state identity; every different or unmatched raw bundle is embedded. Original and complete archives remain untouched.')
    skip={r['archive_path'] for r in rows if r['storage']=='reuse'};expected={k:v for k,v in complete['member_inventory'].items() if k not in skip};seen=set()
    held=Archive(complete['archive']['path'],complete['archive']['sha256'],complete['archive']['bytes'])
    try:
        with tarfile.open(fileobj=held.stream,mode='r|gz') as incoming,tarfile.open(archive_path,'x:gz',compresslevel=1) as outgoing:
            for member in members(incoming,4*1024**3):
                if member.name in skip:
                    with incoming.extractfile(member) as stream:size,sha=digest_stream(stream)
                    need(complete['member_inventory'][member.name]==dict(bytes=size,sha256=sha),'omitted raw source differs');seen.add(member.name);continue
                if member.isfile():
                    with incoming.extractfile(member) as stream:outgoing.addfile(member,stream)
                else:outgoing.addfile(member)
            extra=[(MAP,(json.dumps(manifest,indent=2)+'\n').encode())]+[(n,(HERE/n).read_bytes()) for n in
                   ('restore_ring_live_archive.py','restore_reused_state.py','archive_ring_live_proof.py','test_archive_ring_live_proof.py')]
            for name,raw in extra:
                need(name not in complete['member_inventory'],'added archive path collision')
                info=tarfile.TarInfo(name);info.mode=0o600;info.size=len(raw);outgoing.addfile(info,io.BytesIO(raw))
                expected[name]=dict(bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest())
        held.check()
    finally:held.close()
    need(seen==skip,'missing selected reused raw member')
    need(inventory(archive_path)==expected,'mixed archive independent member verification differs')
    packet=archive_identity(archive_path)
    restored=restore(archive_path,packet['sha256'],None if source is None else Path(source['path']),restore_check)
    verified=[]
    for row in rows:
        target=Path(restore_check)/row['archive_path'];hashes=compare.BUNDLE.read_state(target.parent)
        verified.append(dict(path=str(target),sha256=row['sha256'],bytes=row['bytes'],storage=row['storage'],native_sealed_reader_passed=True,buffer_hash_count=len(hashes)))
    result=dict(schema='ownrt.ring-live-reuse-archive-verification.v1',passed=True,archive=packet,manifest=manifest,
                member_inventory=expected,regular_members=len(expected),restoration_check=restored,restored_sealed_bundles=verified,
                full_archive_preserved=complete['archive'],originals_preserved=True,script=identity(Path(__file__)),
                verified_utc=datetime.now(timezone.utc).isoformat())
    save(receipt_path,result);return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('full')
    for key in ('run','proof','archive','receipt'):a.add_argument('--'+key,type=Path,required=True)
    a=sub.add_parser('reuse')
    for key in ('full-receipt','archive','receipt','restore-check'):a.add_argument('--'+key,type=Path,required=True)
    a.add_argument('--source-durable-receipt',type=Path)
    args=p.parse_args()
    result=full(args.run,args.proof,args.archive,args.receipt) if args.command=='full' else reuse(args.full_receipt,args.source_durable_receipt,args.archive,args.receipt,args.restore_check)
    print(json.dumps({k:result[k] for k in ('passed','archive','regular_members')}))
