#!/usr/bin/env python3
"""Restore deduplicated state bundles inside an already extracted evidence archive.

Makes independent copies: the strict state reader intentionally rejects hardlinks.
Existing destinations, symlinks, path escapes and unauthenticated blobs are refused.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil


def hashed(path):
    total=0;value=hashlib.sha256()
    with path.open('rb') as stream:
        while block:=stream.read(1024*1024):total+=len(block);value.update(block)
    return total,value.hexdigest()


def inside(root,relative):
    path=Path(relative)
    if path.is_absolute() or not path.parts or any(p in ('.','..') for p in path.parts):
        raise ValueError('archive relative path required')
    current=root
    for component in path.parts:
        current/=component
        if current.is_symlink():raise ValueError('archive symlink refused')
    current.resolve().relative_to(root)
    return current


def restore(root):
    root=Path(root).resolve(strict=True)
    manifest_path=inside(root,'state-bundle-map.json')
    if not 0<manifest_path.stat().st_size<=4*1024**2:raise ValueError('manifest size bound')
    manifest=json.loads(manifest_path.read_bytes())
    if manifest['schema']!='ownrt.state-bundle-cas.v1':raise ValueError('manifest schema')
    rows=manifest['bundles']
    if not 0<len(rows)<=4096:raise ValueError('bundle inventory bound')
    destinations=set();blobs={};work=[]
    for row in rows:
        sha=row['sha256'];size=row['bytes']
        if not re.fullmatch('[0-9a-f]{64}',sha) or type(size) is not int or not 0<size<=256*1024**2:
            raise ValueError('bundle hash/size')
        if row['blob']!='blobs/sha256/'+sha:raise ValueError('blob content address')
        source=inside(root,row['blob']);target=inside(root,row['archive_path'])
        if target.name!='state.bundle' or target in destinations or target.exists() or not target.parent.is_dir():
            raise ValueError('fresh unique state.bundle destination required')
        if not source.is_file():raise ValueError('regular blob required')
        destinations.add(target)
        if source not in blobs:blobs[source]=hashed(source)
        if blobs[source]!=(size,sha):raise ValueError('blob digest mismatch')
        work.append((source,target,size,sha))
    if shutil.disk_usage(root).free<sum(r[2] for r in work)+128*1024**2:
        raise ValueError('insufficient free space for independent restored copies')
    for source,target,size,sha in work:
        with source.open('rb') as incoming,target.open('xb') as output:
            shutil.copyfileobj(incoming,output,1024*1024)
        if hashed(target)!=(size,sha):raise ValueError('restored bundle mismatch')
    return dict(restored=len(work),bytes=sum(r[2] for r in work),independent_copies=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',required=True,type=Path)
    print(json.dumps(restore(p.parse_args().root)))
