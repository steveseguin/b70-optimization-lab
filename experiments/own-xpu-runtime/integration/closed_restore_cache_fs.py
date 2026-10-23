#!/usr/bin/env python3
"""Fixed privileged filesystem operations only; no service or native commands.

The unprivileged coordinator owns admission, mount/service checks and repository
receipts. This child accepts no paths or shell commands. All operations are tied
to the frozen eighteen-root inventory and a fresh, exclusive user admission.
"""
from __future__ import annotations
import argparse
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys
import tarfile
import time

HERE=Path(__file__).resolve().parent
FROZEN=HERE/'archive_closed_restore_caches.py'
FROZEN_SHA='36a4929508e7a73f476de31f5bcc29edf49ca3ec49180999822637d97565457a'
if hashlib.sha256(FROZEN.read_bytes()).hexdigest()!=FROZEN_SHA:
    raise RuntimeError('frozen cache archive helper changed')
spec=importlib.util.spec_from_file_location('_privileged_cache_frozen',FROZEN)
A=importlib.util.module_from_spec(spec);spec.loader.exec_module(A)
ROOT=A.ROOT
USER_UID=1000
AGE_SECONDS=120
REC=HERE/'receipts'
PREFIX='closed-restore-caches-privileged'
ARCHIVE=Path('/mnt/usb-models/own-runtime-archives/closed-restore20-28-compiler-caches-20261023-privileged.tar')
SIDECAR=ARCHIVE.with_suffix('.tar.sha256')
COPY_START=REC/(PREFIX+'-copy-start.json')
COPY_RESULT=REC/(PREFIX+'-copy.json')
VERIFY_RESULT=REC/(PREFIX+'-verify.json')
PRUNE_START=REC/(PREFIX+'-prune-start.json')
PRUNE_RESULT=REC/(PREFIX+'-prune.json')
MARKER_NAME='ARCHIVED-torch_compile_cache-20261023-privileged.json'
CHILD=HERE/'closed_restore_cache_fs.py'
COORDINATOR=HERE/'archive_closed_restore_caches_privileged.py'

def source_pins():
    paths=(CHILD,COORDINATOR,HERE/'test_closed_restore_caches_privileged.py',
           HERE/'CLOSED-RESTORE-CACHES-PRIVILEGED.md',FROZEN,A.PARENT,A.U.PARENT,A.INPUT)
    return {str(p.relative_to(ROOT)):A.pin(p)['sha256'] for p in paths}

def key(operation,index=None):
    A.require(operation in ('copy','verify','prune-root'),'fixed operation required')
    if operation=='prune-root':
        A.require(type(index) is int and 0<=index<18,'fixed root index required')
        return f'prune-{index:02d}'
    A.require(index is None,'index forbidden for this operation')
    return operation

def admission_path(operation,index=None):
    return REC/(PREFIX+'-admit-'+key(operation,index)+'.json')

def attempt_path(operation,index=None):
    return ARCHIVE.parent/(ARCHIVE.name+'.'+key(operation,index)+'.attempt.json')

def user_json(path):
    before=A.pin(path);s=path.lstat()
    A.require(s.st_uid==USER_UID and not stat.S_IMODE(s.st_mode)&0o022,
              'coordinator receipt owner/mode refused')
    row=A.read(path)
    A.require(A.pin(path)==before,'coordinator receipt changed during read')
    return row,before

def verify_admission(operation,index=None):
    """Fresh proof is caller attestation; this child never queries services."""
    row,pinned=user_json(admission_path(operation,index))
    A.require(row['schema']=='closed-cache-privileged-admission.v1' and
              row['operation']==operation and row['root_index']==index and
              row['source_sha256']==source_pins(),'admission/source binding mismatch')
    now=time.monotonic();tick=row['monotonic']
    A.require(type(tick) in (int,float) and 0<=now-tick<=AGE_SECONDS,
              'stale or future coordinator admission')
    A.require(row['boot_id']==Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
              'coordinator admission boot changed')
    fixed=A.admitted();proof=row['services']
    A.require(set(proof)==set(fixed['active_units']),'all three current services required')
    for unit,expected in fixed['active_units'].items():
        p=proof[unit]
        A.require(p['active'] is True and type(p['main_pid']) is int and p['main_pid']>0 and
                  p['state_root']==expected['state_root'] and
                  p['working_directory']==expected['working_directory'] and
                  p['argv_sha256']==hashlib.sha256(json.dumps(expected['argv'],separators=(',',':')).encode()).hexdigest(),
                  'current restore29 proof mismatch')
    # Check the exact mount proof supplied by the user, not a subprocess here.
    storage=row['storage']
    A.require(storage['parent']==A.directory(ARCHIVE.parent) and
              storage['parent']==dict(dev=2050,ino=2778419,uid=0,mode=0o777) and
              storage['mount']==dict(target='/mnt/usb-models',source='/dev/sda2',fstype='fuseblk',uuid='4E0E66ED0E66CD91') and
              storage['reserve_bytes']==A.RESERVE and
              storage['free_bytes']>=A.RESERVE+(A.TOTAL+A.ARCHIVE_ALLOWANCE if operation=='copy' else 0),
              'coordinator mount/reserve proof mismatch')
    return fixed,row,pinned

def inventory(fixed):
    files=A.inventory(fixed,hash_files=True)
    for name,row in files.items():
        s=Path(name).lstat()
        row['original_attributes']=dict(uid=s.st_uid,gid=s.st_gid,mode=stat.S_IMODE(s.st_mode))
        A.require(A.stamp(Path(name))==row['stamp'],'source changed while recording attributes')
    return files

def verify_members(stream,files):
    expected={v['archive_member']:v for v in files.values()};seen={}
    stream.seek(0)
    with tarfile.open(fileobj=stream,mode='r:') as tar:
        for member in tar:
            A.require(member.isfile() and member.name in expected and member.name not in seen,
                      'unexpected/duplicate archive member')
            row=expected[member.name];attrs=row['original_attributes']
            A.require(member.size==row['stamp']['bytes'] and
                      dict(uid=member.uid,gid=member.gid,mode=member.mode)==attrs,
                      'archive member extent/attributes mismatch')
            with tar.extractfile(member) as source:digest=A.U.U.sha_stream(source)
            A.require(digest==row['sha256'],'archive member hash mismatch');seen[member.name]=digest
    A.require(set(seen)==set(expected),'incomplete archive')
    return seen

@contextmanager
def verified_archive(files):
    """Exact recovery descriptor stays open until the batch has ended."""
    before=A.pin(ARCHIVE);parent=A.directory(ARCHIVE.parent)
    fd=os.open(ARCHIVE,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        def check():
            s=os.fstat(stream.fileno())
            A.require((s.st_dev,s.st_ino)==(before['stamp']['dev'],before['stamp']['ino']) and
                      A.stamp(ARCHIVE)==before['stamp'] and A.directory(ARCHIVE.parent)==parent,
                      'held recovery archive changed')
        check();members=verify_members(stream,files);stream.seek(0)
        A.require(A.U.U.sha_stream(stream)==before['sha256'],'archive changed during verification')
        check();yield before,members,check

def copy_archive(files,fixed):
    with ARCHIVE.open('xb') as raw:
        with tarfile.open(fileobj=raw,mode='w',format=tarfile.PAX_FORMAT) as tar:
            for name,row in sorted(files.items()):
                path=Path(name)
                A.require(A.directory(path.parent)==fixed['directories'][str(path.parent)] and
                          A.stamp(path)==row['stamp'],'copy source changed')
                fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                with os.fdopen(fd,'rb') as source:
                    s=os.fstat(fd)
                    A.require((s.st_dev,s.st_ino)==(row['stamp']['dev'],row['stamp']['ino']),'copy source replaced')
                    info=tarfile.TarInfo(row['archive_member']);info.size=row['stamp']['bytes']
                    info.mode=row['original_attributes']['mode'];info.uid=row['original_attributes']['uid'];info.gid=row['original_attributes']['gid']
                    tar.addfile(info,source)
                A.require(A.stamp(path)==row['stamp'],'copy source changed during read')
        raw.flush();os.fsync(raw.fileno())
    A.sync_parent(ARCHIVE)

def copy_result():
    row,pinned=user_json(COPY_RESULT)
    A.require(row['passed'] is True and row['phase']=='copy-verified' and
              row['source_sha256']==source_pins() and row['source_rehash_equal'] is True,
              'complete verified copy required')
    return row,pinned

def check_markers(files,copy_pin):
    start,start_pin=user_json(PRUNE_START)
    expected_map={name:row['archive_member'] for name,row in files.items()}
    A.require(start['source_sha256']==source_pins() and start['copy_receipt_sha256']==copy_pin['sha256'] and
              start['restore_map']==expected_map,'durable global restore map mismatch')
    markers={}
    for tree in A.TREES:
        path=tree.parent/MARKER_NAME;row,pinned=user_json(path)
        A.require(row['complete_local_cache'] is False and row['tree']==str(tree) and
                  row['archive']==str(ARCHIVE) and row['copy_receipt_sha256']==copy_pin['sha256'] and
                  row['restore_map']=={n:v for n,v in expected_map.items() if Path(n).is_relative_to(tree)},
                  'complete per-root recovery map required before unlink')
        markers[str(path)]=pinned
    return start_pin,markers

def perform(operation,index=None):
    """Private filesystem seam; main supplies the root/placement boundary."""
    fixed,admission,admission_pin=verify_admission(operation,index)
    A.require(not attempt_path(operation,index).exists(),'prior privileged attempt; no retry')
    result=dict(passed=False,operation=operation,root_index=index,removed_files=[],removed_bytes=0,
                source_sha256=source_pins(),admission_sha256=admission_pin['sha256'])
    try:
        with A.locked() as check_lock:
            if operation=='copy':
                A.require(not any(os.path.lexists(p) for p in (ARCHIVE,SIDECAR,COPY_RESULT,PRUNE_START,PRUNE_RESULT)),
                          'prior archive/result exists; no overwrite')
                files=inventory(fixed)
                verify_admission(operation,index)
                A.write(attempt_path(operation,index),dict(operation=operation,admission_sha256=admission_pin['sha256']))
                copy_archive(files,fixed)
                with verified_archive(files) as (archive_pin,members,check):
                    A.require(inventory(fixed)==files,'original rehash differs')
                    check_lock();check()
                    with SIDECAR.open('x') as out:
                        out.write(archive_pin['sha256']+'  '+ARCHIVE.name+'\n');out.flush();os.fsync(out.fileno())
                    A.sync_parent(SIDECAR);check()
                    result.update(passed=True,phase='copy-verified',files=files,archive_pin=archive_pin,
                                  member_sha256=members,source_rehash_equal=True)
            else:
                copied,copy_pin=copy_result();files=copied['files']
                A.require(set(files)==set(fixed['files']) and
                          all(v['stamp']==fixed['files'][n] for n,v in files.items()),'copy inventory differs')
                with verified_archive(files) as (archive_pin,members,check):
                    A.require(archive_pin==copied['archive_pin'] and members==copied['member_sha256'] and
                              SIDECAR.read_text()==archive_pin['sha256']+'  '+ARCHIVE.name+'\n',
                              'recovery archive differs from verified copy')
                    if operation=='verify':
                        A.require(inventory(fixed)==files,'all originals must match before markers')
                        verify_admission(operation,index);check_lock();check()
                        A.write(attempt_path(operation,index),dict(operation=operation,admission_sha256=admission_pin['sha256']))
                        result.update(passed=True,phase='all-originals-and-archive-verified',copy_receipt_sha256=copy_pin['sha256'])
                    else:
                        verified,verify_pin=user_json(VERIFY_RESULT)
                        A.require(verified['passed'] is True and verified['phase']=='all-originals-and-archive-verified' and
                                  verified['copy_receipt_sha256']==copy_pin['sha256'],'full pre-prune verification required')
                        start_pin,markers=check_markers(files,copy_pin)
                        tree=A.TREES[index]
                        verify_admission(operation,index);check_lock();check()
                        A.write(attempt_path(operation,index),dict(operation=operation,root_index=index,admission_sha256=admission_pin['sha256']))
                        for name,row in sorted(files.items()):
                            path=Path(name)
                            if not path.is_relative_to(tree):continue
                            check();check_lock()
                            A.require(A.directory(path.parent)==fixed['directories'][str(path.parent)] and
                                      A.pin(path)=={k:row[k] for k in ('stamp','sha256')},'source changed before unlink')
                            fd=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
                            try:
                                s=os.fstat(fd);parent=fixed['directories'][str(path.parent)]
                                A.require((s.st_dev,s.st_ino)==(parent['dev'],parent['ino']),'unlink parent replaced')
                                s=os.stat(path.name,dir_fd=fd,follow_symlinks=False)
                                A.require(stat.S_ISREG(s.st_mode) and s.st_nlink==1 and
                                          (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)==
                                          tuple(row['stamp'][k] for k in ('dev','ino','bytes','mtime_ns','ctime_ns')),
                                          'file changed at unlink')
                                check();os.unlink(path.name,dir_fd=fd);os.fsync(fd)
                            finally:os.close(fd)
                            result['removed_files'].append(name);result['removed_bytes']+=row['stamp']['bytes']
                        check_lock();check()
                        A.require(user_json(PRUNE_START)[1]==start_pin and
                                  all(user_json(Path(p))[1]==v for p,v in markers.items()),'recovery markers changed')
                        result.update(passed=True,phase='root-pruned',copy_receipt_sha256=copy_pin['sha256'])
            A.require(source_pins()==result['source_sha256'],'source changed during privileged operation')
    except BaseException as error:
        result.update(passed=False,error_type=type(error).__name__,error=str(error)[:4096])
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--operation',choices=('copy','verify','prune-root'),required=True)
    parser.add_argument('--root-index',type=int,choices=range(18))
    args=parser.parse_args();key(args.operation,args.root_index)
    A.require(os.geteuid()==0,'fixed filesystem child requires elevated uid')
    A.require(sys.flags.isolated and Path(sys.executable)==Path('/usr/bin/python3'),'isolated system interpreter required')
    A.placement()
    result=perform(args.operation,args.root_index)
    print(json.dumps(result,separators=(',',':')),flush=True)
    return 0 if result['passed'] else 1

if __name__=='__main__':raise SystemExit(main())
