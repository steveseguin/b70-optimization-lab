#!/usr/bin/env python3
"""Fixed archive of eighteen CLOSED restore20..28 compiler caches. Never deletes."""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=HERE/'archive_p199_checkpoints.py'
PARENT_SHA='46710ec916aea75a11ee22679f1f18220eecb5d62cd0e300fafddbd93f80aba0'
if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PARENT_SHA:
    raise RuntimeError('pinned archive primitives changed')
spec=importlib.util.spec_from_file_location('_closed_cache_archive_primitives',PARENT)
U=importlib.util.module_from_spec(spec);spec.loader.exec_module(U)
require,pin,stamp,directory,utc=U.require,U.pin,U.stamp,U.directory,U.utc
write,sync_parent,placement=U.write,U.sync_parent,U.placement
INPUT=HERE/'receipts/closed-restore-caches-inputs.json'
INPUT_SHA='9bc047db8d4ee3c8f969143b9a7ace8848a6379f004658b1f6633feccd4c2c19'
BASE=Path('/home/steve/inference')
TREES=tuple(BASE/f'qwen38-27b-fp8-card{c}-20261023-restore{n}'/'cache/torch_compile_cache'
            for n in range(20,29) for c in (0,3))
ARCHIVE=Path('/mnt/usb-models/own-runtime-archives/closed-restore20-28-compiler-caches-20261023.tar')
SIDECAR=ARCHIVE.with_suffix('.tar.sha256')
START=HERE/'receipts/closed-restore-caches-archive-start.json'
RECEIPT=HERE/'receipts/closed-restore-caches-archive.json'
PRUNE_START=HERE/'receipts/closed-restore-caches-prune-start.json'
PRUNE_RECEIPT=HERE/'receipts/closed-restore-caches-prune.json'
MARKER_NAME='ARCHIVED-torch_compile_cache-20261023.json'
TOTAL=1070345088
COUNT=8766
RESERVE=50*1024**3
ARCHIVE_ALLOWANCE=32*1024**2

def read(path):
    require(stamp(path)['bytes']<=32*1024**2,'JSON receipt exceeds bound')
    with Path(path).open() as f:return json.load(f)

def admitted():
    require(pin(INPUT)['sha256']==INPUT_SHA,'fixed cache inventory changed')
    row=read(INPUT)
    require(row['trees']==[str(p) for p in TREES] and row['total_bytes']==TOTAL and
            row['files_count']==COUNT and len(row['files'])==COUNT,'fixed inventory scope changed')
    for name,digest in row['closure_sha256'].items():
        require(pin(ROOT/name)['sha256']==digest,'closure/restore29 evidence changed')
    return row

def code_pins():
    paths=[Path(__file__),HERE/'prune_closed_restore_caches.py',PARENT,U.PARENT,INPUT]
    return {str(p):pin(p)['sha256'] for p in paths}

def check_directories(expected):
    for name,identity in expected.items():
        require(directory(Path(name))==identity,'fixed directory identity changed')

def inventory(fixed,*,hash_files):
    """No following aliases, hardlinks, cross-device directories or added files."""
    check_directories(fixed['directories'])
    found={};seen_dirs=set();inodes=set()
    for tree in TREES:
        for root,dirs,files in os.walk(tree,followlinks=False):
            root=Path(root);seen_dirs.add(str(root))
            require(str(root) in fixed['directories'],'unexpected directory')
            require(directory(root)==fixed['directories'][str(root)],'changed directory')
            for name in dirs:
                p=root/name
                require(str(p) in fixed['directories'] and not p.is_symlink(),'unexpected/aliased directory')
            for name in files:
                p=root/name;n=str(p)
                require(n in fixed['files'],'unexpected cache file')
                require(p.resolve()==p,'aliased file path')
                s=stamp(p);require(s==fixed['files'][n],'cache file metadata changed')
                require(s['dev']==fixed['directories'][str(tree)]['dev'],'cache crosses filesystem')
                key=(s['dev'],s['ino']);require(key not in inodes,'duplicate cache inode');inodes.add(key)
                found[n]=dict(stamp=s,archive_member=p.relative_to(BASE).as_posix())
                if hash_files:
                    hashed=pin(p);require(hashed['stamp']==s,'cache changed before hash')
                    found[n]['sha256']=hashed['sha256']
    required_dirs={n for n in fixed['directories'] if any(Path(n).is_relative_to(t) for t in TREES)}
    require(seen_dirs==required_dirs and set(found)==set(fixed['files']),'incomplete cache inventory')
    require(len(found)==COUNT and sum(v['stamp']['bytes'] for v in found.values())==TOTAL,'cache extent/count mismatch')
    return found

def current_services(fixed,*,runner=subprocess.run):
    """Read only the current unit configuration; never request or print Environment."""
    proof={}
    for unit,expected in fixed['active_units'].items():
        cp=runner(['systemctl','--user','show',unit+'.service',
            '--property=ActiveState,SubState,MainPID,ExecStart,WorkingDirectory'],
            capture_output=True,text=True,timeout=15)
        require(cp.returncode==0 and len(cp.stdout)<=32768,'current service configuration unavailable')
        rows={}
        for line in cp.stdout.splitlines():
            require('=' in line,'malformed current service configuration')
            k,v=line.split('=',1);require(k not in rows,'duplicate current service property');rows[k]=v
        require(set(rows)=={'ActiveState','SubState','MainPID','ExecStart','WorkingDirectory'},'unexpected current service properties')
        require(rows['ActiveState']=='active' and rows['SubState']=='running' and
                re.fullmatch(r'[1-9][0-9]*',rows['MainPID']) is not None,'restore29 service not running')
        matches=re.findall(r'argv\[\]=([^;{}]*);',rows['ExecStart'])
        require(len(matches)==1,'ambiguous current ExecStart')
        try:argv=shlex.split(matches[0])
        except ValueError:raise RuntimeError('malformed current ExecStart') from None
        require(argv==expected['argv'] and rows['WorkingDirectory']==expected['working_directory'],
                'current service no longer uses admitted restore29 argv/directory')
        target=expected['state_root']
        require(target.endswith('-20261023-restore29') and
                (('--state-dir' in argv and argv[argv.index('--state-dir')+1]==target) or
                 (unit=='qwen38-27b-vision' and rows['WorkingDirectory']==target)),
                'restore29 state path mismatch')
        proof[unit]=dict(main_pid=int(rows['MainPID']),state_root=target,
            argv_sha256=hashlib.sha256(json.dumps(argv,separators=(',',':')).encode()).hexdigest(),
            working_directory=rows['WorkingDirectory'],active=True)
    require(len(proof)==3,'all three current services required')
    return proof

def storage(*,before_copy=False,runner=subprocess.run):
    identity=directory(ARCHIVE.parent)
    require(identity==dict(dev=2050,ino=2778419,uid=0,mode=0o777),'archive parent changed')
    cp=runner(['findmnt','-T',str(ARCHIVE.parent),'-J','-o','TARGET,SOURCE,FSTYPE,UUID'],
              capture_output=True,text=True,timeout=15)
    require(cp.returncode==0 and len(cp.stdout)<=4096,'archive mount query failed')
    mount=json.loads(cp.stdout)['filesystems']
    require(mount==[dict(target='/mnt/usb-models',source='/dev/sda2',fstype='fuseblk',uuid='4E0E66ED0E66CD91')],
            'archive mount identity changed')
    free=shutil.disk_usage(ARCHIVE.parent).free
    require(free>=RESERVE+(TOTAL+ARCHIVE_ALLOWANCE if before_copy else 0),'50GiB external reserve refused')
    return dict(parent=identity,mount=mount[0],free_bytes=free,reserve_bytes=RESERVE)

@contextmanager
def locked():
    before=stamp(INPUT);fd=os.open(INPUT,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        def check():
            s=os.fstat(fd)
            require((s.st_dev,s.st_ino)==(before['dev'],before['ino']) and stamp(INPUT)==before,'input lock changed')
        check();yield check
    finally:os.close(fd)

def verify_members(stream,files):
    expected={v['archive_member']:v for v in files.values()};seen={}
    stream.seek(0)
    with tarfile.open(fileobj=stream,mode='r:') as tar:
        for member in tar:
            require(member.isfile() and member.name in expected and member.name not in seen,'unexpected/duplicate archive member')
            row=expected[member.name];require(member.size==row['stamp']['bytes'],'archive member extent mismatch')
            with tar.extractfile(member) as src:digest=U.U.sha_stream(src)
            require(digest==row['sha256'],'archive member hash mismatch');seen[member.name]=digest
    require(set(seen)==set(expected),'incomplete archive')
    return seen

@contextmanager
def verified_archive(files):
    before=pin(ARCHIVE);parent=directory(ARCHIVE.parent)
    fd=os.open(ARCHIVE,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        def check():
            s=os.fstat(stream.fileno())
            require((s.st_dev,s.st_ino)==(before['stamp']['dev'],before['stamp']['ino']) and
                    stamp(ARCHIVE)==before['stamp'] and directory(ARCHIVE.parent)==parent,'held recovery archive changed')
        check();members=verify_members(stream,files);stream.seek(0)
        require(U.U.sha_stream(stream)==before['sha256'],'archive changed during verification')
        check();yield before,members,check

def copy_archive(files,fixed):
    with ARCHIVE.open('xb') as raw:
        with tarfile.open(fileobj=raw,mode='w',format=tarfile.PAX_FORMAT) as tar:
            for name,row in sorted(files.items()):
                p=Path(name)
                require(directory(p.parent)==fixed['directories'][str(p.parent)] and stamp(p)==row['stamp'],'copy source changed')
                fd=os.open(p,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                with os.fdopen(fd,'rb') as src:
                    s=os.fstat(fd);require((s.st_dev,s.st_ino)==(row['stamp']['dev'],row['stamp']['ino']),'source replaced during open')
                    info=tarfile.TarInfo(row['archive_member']);info.size=row['stamp']['bytes'];info.mode=0o600
                    tar.addfile(info,src)
                require(stamp(p)==row['stamp'],'source changed during copy')
        raw.flush();os.fsync(raw.fileno())
    sync_parent(ARCHIVE)

def copy_verify():
    placement()
    with locked() as check_lock:
        require(not any(os.path.lexists(p) for p in (ARCHIVE,SIDECAR,START,RECEIPT,PRUNE_START,PRUNE_RECEIPT)),
                'prior operation/destination exists; preserve and review, no retry')
        fixed=admitted();codes=code_pins();services=current_services(fixed);mount=storage(before_copy=True)
        files=inventory(fixed,hash_files=True)
        row=dict(schema='closed-restore-caches-archive.v1',passed=False,started_utc=utc(),archive=str(ARCHIVE),
                 source_sha256=codes,files=files,closure=fixed['closure'],initial_services=services,storage=mount,
                 deleted_files=0,restore_map={n:v['archive_member'] for n,v in files.items()})
        write(START,row)
        try:
            copy_archive(files,fixed)
            with verified_archive(files) as (archive_pin,members,check_archive):
                require(inventory(fixed,hash_files=True)==files,'original rehash mismatch')
                require(code_pins()==codes,'archive implementation changed')
                row['final_services']=current_services(fixed);storage();check_lock();check_archive()
                with SIDECAR.open('x') as side:
                    side.write(archive_pin['sha256']+'  '+ARCHIVE.name+'\n');side.flush();os.fsync(side.fileno())
                sync_parent(SIDECAR);check_archive()
                row.update(passed=True,archive_pin=archive_pin,member_sha256=members,
                           source_rehash_equal=True,finished_utc=utc(),phase='verified-copy-only')
        except BaseException as error:
            row.update(passed=False,error_type=type(error).__name__,error=str(error)[:4096],phase='failed-copy-preserved')
            write(RECEIPT,row);raise
        write(RECEIPT,row)
    return row

def main():
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--plan',action='store_true');g.add_argument('--copy-verify',action='store_true');a=p.parse_args();placement()
    if a.plan:
        fixed=admitted();files=inventory(fixed,hash_files=False)
        row=dict(read_only=True,service_queries_executed=False,cache_contents_read=False,files=len(files),
                 bytes=TOTAL,archive=str(ARCHIVE),roots=[str(p) for p in TREES],external_reserve_bytes=RESERVE,
                 closure=fixed['closure'],source_sha256=code_pins())
    else:
        result=copy_verify();row={k:result[k] for k in ('passed','phase','archive','deleted_files')}
    print(json.dumps(row,indent=2))

if __name__=='__main__':main()
