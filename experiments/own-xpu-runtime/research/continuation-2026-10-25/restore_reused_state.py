#!/usr/bin/env python3
"""Restore a hash-pinned metadata archive using sealed bytes from an older archive.

Never uses tar.extract, hardlinks, symlinks, or overwrites existing paths.
Archives are read through stable regular-file descriptors. A failed restore leaves
its fresh partial directory for inspection; it is never reused automatically.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import tarfile


def need(ok, why):
    if not ok:raise ValueError(why)


def relative(name):
    need(isinstance(name,str) and name and '\\' not in name and '\0' not in name,'relative archive name required')
    p=PurePosixPath(name)
    need(not p.is_absolute() and str(p)==name and not any(x in ('.','..') for x in p.parts),'unsafe archive path')
    return p


def digest_stream(stream, output=None):
    count=0;h=hashlib.sha256()
    while block:=stream.read(1024*1024):
        count+=len(block);h.update(block)
        if output is not None:output.write(block)
    return count,h.hexdigest()


def identity(st):return (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns)


class Archive:
    def __init__(self,path,expected_sha,expected_size=None,limit=4*1024**3):
        need(re.fullmatch('[0-9a-f]{64}',expected_sha) is not None,'independent archive SHA required')
        self.path=Path(path)
        fd=os.open(self.path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
        self.stream=os.fdopen(fd,'rb')
        try:
            self.before=os.fstat(fd)
            need(stat.S_ISREG(self.before.st_mode) and 0<self.before.st_size<=limit,'bounded regular archive required')
            count,sha=digest_stream(self.stream)
            need(sha==expected_sha and (expected_size is None or count==expected_size),'archive checksum/size differs')
            self.check();self.stream.seek(0)
        except BaseException:self.stream.close();raise
    def check(self):
        current=os.fstat(self.stream.fileno());named=self.path.lstat()
        need(stat.S_ISREG(named.st_mode) and identity(current)==identity(self.before)==identity(named),'archive changed/rebound during read')
    def close(self):self.stream.close()


def members(archive,max_total):
    names=set();total=0
    for member in archive:
        # Python tarfile strips trailing slash from directory names on reading.
        relative(member.name)
        need(member.name not in names and len(names)<20000,'duplicate or excessive archive members')
        names.add(member.name)
        need(member.isdir() or member.isfile(),'links and special archive members refused')
        need(type(member.size) is int and 0<=member.size<=256*1024**2,'member extent bound')
        total+=member.size
        need(total<=max_total,'expanded archive size bound')
        yield member


def destination(root,name):
    p=root.joinpath(*relative(name).parts)
    current=root
    for part in p.relative_to(root).parts[:-1]:
        current/=part
        if current.exists() or current.is_symlink():need(current.is_dir() and not current.is_symlink(),'non-directory archive ancestor')
        else:current.mkdir(mode=0o700)
    need(not p.exists() and not p.is_symlink(),'fresh independent file required')
    return p


def write_new(path,stream):
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as out:return digest_stream(stream,out)


def file_hash(path):
    with path.open('rb') as f:return digest_stream(f)


def restore(metadata_archive,metadata_sha256,raw_archive,out):
    out=Path(out).absolute()
    need(out.parent.is_dir() and out.parent.resolve()==out.parent and not out.exists() and not out.is_symlink(),
         'fresh output under canonical existing parent required')
    metadata=Archive(metadata_archive,metadata_sha256,limit=64*1024**2)
    try:
        out.mkdir(mode=0o700)
        with tarfile.open(fileobj=metadata.stream,mode='r|gz') as archive:
            for member in members(archive,128*1024**2):
                need(PurePosixPath(member.name).name!='state.bundle','metadata archive must not contain raw state')
                path=out.joinpath(*relative(member.name).parts)
                if member.isdir():
                    if path.exists():need(path.is_dir() and not path.is_symlink(),'directory collision')
                    else:path.mkdir(mode=0o700,parents=True)
                else:
                    path=destination(out,member.name)
                    with archive.extractfile(member) as stream:count,_=write_new(path,stream)
                    need(count==member.size,'metadata member truncation')
        metadata.check()
    finally:metadata.close()
    manifest_path=out/'reused-state-map.json'
    need(manifest_path.is_file() and 0<manifest_path.stat().st_size<=4*1024**2,'bounded reuse manifest required')
    manifest=json.loads(manifest_path.read_text())
    need(manifest['schema']=='ownrt.reused-state-archive.v1','reuse manifest schema')
    rows=manifest['bundles'];need(isinstance(rows,list) and 0<len(rows)<=4096,'bounded bundle inventory required')
    expected={};targets=set();work={}
    for row in rows:
        target=destination(out,row['archive_path'])
        need(target.name=='state.bundle' and target not in targets,'unique raw-state destination required')
        targets.add(target)
        need(type(row['bytes']) is int and 0<row['bytes']<=256*1024**2 and re.fullmatch('[0-9a-f]{64}',row['sha256']),
             'raw state extent/hash')
        source=str(relative(row['source_member']))
        need(source.endswith('/state.bundle'),'raw source member name')
        expected.setdefault(source,(row['bytes'],row['sha256']))
        need(expected[source]==(row['bytes'],row['sha256']),'conflicting shared source identity')
        work.setdefault(source,[]).append(target)
        need(set(row['metadata_sha256'])=={'state-seal.txt','state-index.tsv','state.json'},'complete sealed metadata required')
        for name,sha in row['metadata_sha256'].items():
            need(re.fullmatch('[0-9a-f]{64}',sha) and file_hash(target.parent/name)[1]==sha,'retained seal/index/state metadata differs')
            source_meta=str(PurePosixPath(source).parent/name)
            expected.setdefault(source_meta,(None,sha))
            need(expected[source_meta]==(None,sha),'source metadata identity conflict')
    need(os.statvfs(out).f_bavail*os.statvfs(out).f_frsize>=sum(r['bytes'] for r in rows)+128*1024**2,
         'insufficient free space for independent state copies')
    source=manifest['source_archive']
    raw=Archive(raw_archive,source['sha256'],source['bytes'])
    seen=set();inodes=set()
    try:
        with tarfile.open(fileobj=raw.stream,mode='r|gz') as archive:
            for member in members(archive,4*1024**3):
                if member.name not in expected:continue
                need(member.isfile() and member.name not in seen,'expected regular unique source member')
                size,sha=expected[member.name]
                with archive.extractfile(member) as stream:
                    if member.name in work:
                        # Independent files, even when two destinations reuse one source.
                        paths=work[member.name];fds=[]
                        try:
                            for path in paths:
                                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
                                fds.append(os.fdopen(fd,'wb'))
                            n=0;h=hashlib.sha256()
                            while block:=stream.read(1024*1024):
                                n+=len(block);h.update(block)
                                for f in fds:f.write(block)
                            observed=h.hexdigest()
                        finally:
                            for f in fds:f.close()
                    else:n,observed=digest_stream(stream)
                need(n==member.size and (size is None or n==size) and observed==sha,'reused source member bytes differ')
                seen.add(member.name)
        raw.check()
    finally:raw.close()
    need(seen==set(expected),'source archive missing referenced raw/sealed metadata')
    for row in rows:
        path=out.joinpath(*relative(row['archive_path']).parts);st=path.lstat()
        need(stat.S_ISREG(st.st_mode) and st.st_nlink==1 and (st.st_dev,st.st_ino) not in inodes,'restored bytes must be independent regular files')
        inodes.add((st.st_dev,st.st_ino))
        need(file_hash(path)==(row['bytes'],row['sha256']),'restored raw bytes differ')
    return dict(schema='ownrt.reused-state-restore.v1',passed=True,restored=len(rows),
                raw_bytes=sum(r['bytes'] for r in rows),independent_copies=True,metadata_sha256=metadata_sha256,
                source_archive_sha256=source['sha256'],output=str(out))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--metadata-archive',required=True,type=Path);p.add_argument('--metadata-sha256',required=True)
    p.add_argument('--raw-archive',required=True,type=Path);p.add_argument('--out',required=True,type=Path)
    a=p.parse_args();print(json.dumps(restore(a.metadata_archive,a.metadata_sha256,a.raw_archive,a.out),indent=2))
