#!/usr/bin/env python3
"""Restore explicit mixed embedded/reused ring-live state as independent files.

New schema only. Old target-only archive semantics remain unchanged. Authenticate
both archives, refuse missing or unlisted raw state, and never overwrite/delete.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile

from restore_reused_state import Archive, destination, digest_stream, file_hash, members, need, relative, write_new

MAP='ring-live-state-map.json'
META=('state-seal.txt','state-index.tsv','state.json')


def pairs(items):
    out={}
    for key,value in items:
        need(key not in out,'duplicate JSON key');out[key]=value
    return out


def validate_manifest(manifest,embedded):
    need(manifest.get('schema')=='ownrt.ring-live-reuse-archive.v1','explicit ring-live archive schema required')
    rows=manifest['bundles'];need(isinstance(rows,list) and 0<len(rows)<=64,'bounded complete raw-state inventory')
    seen=set();expected={};work={}
    for row in rows:
        target=str(relative(row['archive_path']))
        need(PurePosixPath(target).name=='state.bundle' and target not in seen,'unique raw-state path required');seen.add(target)
        need(type(row['bytes']) is int and 0<row['bytes']<=256*1024**2
             and re.fullmatch('[0-9a-f]{64}',row['sha256']) is not None,'raw-state size/digest required')
        need(set(row['metadata_sha256'])==set(META)
             and all(re.fullmatch('[0-9a-f]{64}',v) for v in row['metadata_sha256'].values()),'complete sealed metadata hashes')
        if row['storage']=='embedded':
            need(embedded.get(target)==(row['bytes'],row['sha256']),'embedded raw missing or differs')
            need('source_member' not in row,'embedded state cannot name external raw')
        else:
            need(row['storage']=='reuse' and target not in embedded,'explicit reused state must be absent from packet')
            source=str(relative(row['source_member']));need(PurePosixPath(source).name=='state.bundle','raw source member required')
            for name,want in [(source,(row['bytes'],row['sha256']))]+[(str(PurePosixPath(source).parent/n),(None,h)) for n,h in row['metadata_sha256'].items()]:
                need(name not in expected or expected[name]==want,'conflicting source identity');expected[name]=want
            work.setdefault(source,[]).append(target)
    need(set(embedded)=={r['archive_path'] for r in rows if r['storage']=='embedded'},'unlisted raw payload in packet')
    return rows,expected,work


def restore(packet,packet_sha256,source_archive,out):
    out=Path(out).absolute()
    need(out.parent.is_dir() and out.parent.resolve()==out.parent and not out.exists() and not out.is_symlink(),
         'fresh output below canonical existing parent required')
    held=Archive(packet,packet_sha256)
    try:
        manifest=None;embedded={};expanded=0
        with tarfile.open(fileobj=held.stream,mode='r|gz') as archive:
            for member in members(archive,4*1024**3):
                expanded+=member.size
                if member.name==MAP:
                    need(member.isfile() and member.size<=4*1024**2,'bounded manifest required')
                    manifest=json.loads(archive.extractfile(member).read(),object_pairs_hook=pairs)
                elif PurePosixPath(member.name).name=='state.bundle':
                    need(member.isfile(),'regular raw member required')
                    with archive.extractfile(member) as stream:embedded[member.name]=digest_stream(stream)
        held.check();need(manifest is not None,'missing mixed archive manifest')
        rows,expected,work=validate_manifest(manifest,embedded)
        need(not expected or source_archive is not None,'reused state requires source archive')
        available=os.statvfs(out.parent);required=expanded+sum(r['bytes'] for r in rows if r['storage']=='reuse')+16*1024**2
        need(available.f_bavail*available.f_frsize>=required,'insufficient free space for independent restoration')
        out.mkdir(mode=0o700);held.stream.seek(0)
        with tarfile.open(fileobj=held.stream,mode='r|gz') as archive:
            for member in members(archive,4*1024**3):
                path=out.joinpath(*relative(member.name).parts)
                if member.isdir():
                    if path.exists():need(path.is_dir() and not path.is_symlink(),'directory collision')
                    else:path.mkdir(mode=0o700,parents=True)
                else:
                    path=destination(out,member.name)
                    with archive.extractfile(member) as stream:n,_=write_new(path,stream)
                    need(n==member.size,'packet member truncated')
        held.check()
    finally:held.close()
    for row in rows:
        parent=(out/row['archive_path']).parent
        for name,digest in row['metadata_sha256'].items():need(file_hash(parent/name)[1]==digest,'retained sealed metadata differs')
    if expected:
        source=manifest['source_archive'];held=Archive(source_archive,source['sha256'],source['bytes']);seen=set()
        try:
            with tarfile.open(fileobj=held.stream,mode='r|gz') as archive:
                for member in members(archive,4*1024**3):
                    if member.name not in expected:continue
                    need(member.isfile(),'referenced regular member required');size,digest=expected[member.name]
                    if member.name in work:
                        streams=[]
                        try:
                            for name in work[member.name]:
                                path=destination(out,name);fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                                streams.append(os.fdopen(fd,'wb'))
                            count=0;h=hashlib.sha256()
                            with archive.extractfile(member) as incoming:
                                while block:=incoming.read(1024*1024):
                                    count+=len(block);h.update(block)
                                    for output in streams:output.write(block)
                            observed=h.hexdigest()
                        finally:
                            for output in streams:output.close()
                    else:
                        with archive.extractfile(member) as stream:count,observed=digest_stream(stream)
                    need(count==member.size and (size is None or size==count) and observed==digest,'reused source raw/metadata differs')
                    seen.add(member.name)
            held.check();need(seen==set(expected),'source archive lacks referenced raw/metadata')
        finally:held.close()
    inodes=set()
    for row in rows:
        path=out/row['archive_path'];st=path.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and (st.st_dev,st.st_ino) not in inodes,'independent single-link raw copies required')
        inodes.add((st.st_dev,st.st_ino));need(file_hash(path)==(row['bytes'],row['sha256']),'restored raw bytes differ')
    return dict(schema='ownrt.ring-live-archive-restore.v1',passed=True,restored=len(rows),
                reused=sum(r['storage']=='reuse' for r in rows),embedded=sum(r['storage']=='embedded' for r in rows),
                raw_bytes=sum(r['bytes'] for r in rows),independent_copies=True,packet_sha256=packet_sha256,output=str(out))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',required=True,type=Path);p.add_argument('--sha256',required=True)
    p.add_argument('--source-archive',type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(json.dumps(restore(a.archive,a.sha256,a.source_archive,a.out),indent=2))
