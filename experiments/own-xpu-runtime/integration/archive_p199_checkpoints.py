#!/usr/bin/env python3
"""Fixed closed-p199 archive. Plan is metadata-only; copy never deletes originals."""
from __future__ import annotations
import argparse
from contextlib import contextmanager, ExitStack
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tarfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PARENT=HERE/'archive_p184_checkpoints.py'
PARENT_SHA='4d84e566824579c5d8f6ee264d59f4638deddfa2dbbab6e2fea53539c0a8d8f7'
if hashlib.sha256(PARENT.read_bytes()).hexdigest()!=PARENT_SHA:
    raise RuntimeError('frozen p184 archive utility changed')
spec=importlib.util.spec_from_file_location('_p199_frozen_archive_primitives',PARENT)
U=importlib.util.module_from_spec(spec);spec.loader.exec_module(U)
require,stamp,pin,utc=U.require,U.stamp,U.pin,U.utc
PACKET=ROOT/'experiments/own-xpu-runtime/stage2/packet199-chat-parking'
EVIDENCE=PACKET/'evidence'
CHECKPOINTS=EVIDENCE/'runcheckpoints'
IDS=('p199-a-7c4609adccb5044b2ca331a8','p199-fresh-11d2d955e66fc33761c0328e')
ARCHIVE=Path('/mnt/usb-models/own-runtime-archives/p199-closed-checkpoints-20261023.tar')
SIDECAR=ARCHIVE.with_suffix('.tar.sha256')
RECEIPT=EVIDENCE/'checkpoint-archive-20261023.json'
PRUNE_RECEIPT=EVIDENCE/'checkpoint-local-prune-20261023.json'
MARKER=EVIDENCE/'ARCHIVED-CHECKPOINTS-20261023.json'
TENSOR_BYTES=146964480
TOTAL_BYTES=147737106
GUARD_PINS={
 'experiments/own-xpu-runtime/stage2/packet199-chat-parking/evidence/independent-device-result.json':'335e914aa0cf3db7ee02ec5bec36248382937e049fe80b3ad6bec133f45a3019',
 'experiments/own-xpu-runtime/stage2/packet199-chat-parking/evidence/independent-restore28-review.json':'211bb2e3a95038873065ce4eb3e0808dab5673e7d649b5e3ef43ba855feb7e75',
 'experiments/own-xpu-runtime/stage2/packet199-chat-parking/evidence/independent-restore28-observations.json':'1c97fd64610cee5e124fda86da28c6e8efe3b3a4e121d4548a808c8fc6fb763e',
 'experiments/own-xpu-runtime/stage2/packet199-chat-parking/evidence/device-p199-chat-A-a/worker.json':'c40defd454c129cb2f95c8ec1817b4c145eee24d3947792d8b981e6c29ac6f04',
 'experiments/own-xpu-runtime/ops/packet199-window/evidence/window-a/window-result.json':'5d9f7a26a4a48ba1d8b971cc32ecfc1efc0b2fc1d69a666fb272b94da7cc504b',
 'experiments/own-xpu-runtime/ops/packet199-window/evidence/window-a/postflight-drain.json':'65eaf399486cc3e635b12287d6282c2b88ecb28a78576880e4ec7f169fcfcda0',
}

def rel(path):return Path(path).relative_to(ROOT).as_posix()
def read(path):return json.loads(Path(path).read_text())
def sync_parent(path):
    """Persist the newly named file; unsupported directory fsync is a refusal."""
    parent=Path(path).parent
    before=directory(parent)
    fd=os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        s=os.fstat(fd)
        require((s.st_dev,s.st_ino)==(before['dev'],before['ino']),'parent replaced before fsync')
        os.fsync(fd)
        require(directory(parent)==before,'parent changed during fsync')
    finally:os.close(fd)

def write(path,row,mode='x'):
    with Path(path).open(mode) as file:
        json.dump(row,file,indent=2,ensure_ascii=False);file.write('\n');file.flush();os.fsync(file.fileno())
    sync_parent(path)

def directory(path):
    require(path.resolve()==path,'aliased directory')
    s=path.lstat();require(stat.S_ISDIR(s.st_mode),'not a directory')
    return dict(dev=s.st_dev,ino=s.st_ino,uid=s.st_uid,mode=stat.S_IMODE(s.st_mode))

def storage():
    identity=directory(ARCHIVE.parent)
    require(identity==dict(dev=2050,ino=2778419,uid=0,mode=0o777),'archive parent identity changed')
    cp=subprocess.run(['findmnt','-T',str(ARCHIVE.parent),'-J','-o','TARGET,SOURCE,FSTYPE,UUID'],
                      capture_output=True,text=True,timeout=15,check=True)
    mount=json.loads(cp.stdout)['filesystems']
    require(len(mount)==1 and mount[0]==dict(target='/mnt/usb-models',source='/dev/sda2',
            fstype='fuseblk',uuid='4E0E66ED0E66CD91'),'archive mount identity changed')
    free=shutil.disk_usage(ARCHIVE.parent).free
    require(free>=TOTAL_BYTES+1024**3,'external archive headroom refused')
    return dict(parent=identity,mount=mount[0],free_bytes=free,root_free_bytes=shutil.disk_usage(ROOT).free)

def closed_guards():
    guards={name:pin(ROOT/name) for name in GUARD_PINS}
    require(all(guards[n]['sha256']==v for n,v in GUARD_PINS.items()),'closed result/restore evidence changed')
    worker=read(EVIDENCE/'device-p199-chat-A-a/worker.json')
    window=read(ROOT/'experiments/own-xpu-runtime/ops/packet199-window/evidence/window-a/window-result.json')
    audit=read(EVIDENCE/'independent-device-result.json')
    require(worker['passed'] is True and worker['safe_to_exit'] is True and worker['devices_drained'] is True
            and worker['child_still_running'] is False and window['passed'] is True
            and window['restore_suffix']=='20261023-restore28' and window['worker']==worker
            and audit['passed'] is True and audit['worker_drain_passed'] is True,'closed owner proof failed')
    for path in (Path(__file__),HERE/'prune_p199_checkpoints.py',PARENT):guards[rel(path)]=pin(path)
    return guards,audit

def no_owner():
    for unit in ('packet199-chat-parking-a','window-p199-driver'):
        cp=subprocess.run(['systemctl','--user','show',unit+'.service','--property=ActiveState,MainPID'],
                          capture_output=True,text=True,timeout=15)
        row=dict(line.split('=',1) for line in cp.stdout.splitlines() if '=' in line)
        require(cp.returncode==0 and row.get('ActiveState')=='inactive' and row.get('MainPID')=='0',
                'historical p199 owner/window is not inactive')
    require(not Path('/proc/3431024').exists(),'historical owner PID exists; review before archive')

@contextmanager
def locked():
    """Existing native lockfiles only, exclusive and nonblocking; never create."""
    held=[];identities=[]
    try:
        no_owner()
        for cid in IDS:
            path=CHECKPOINTS/(cid+'.lock');before=stamp(path)
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC);held.append(fd)
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            s=os.fstat(fd)
            require((s.st_dev,s.st_ino)==(before['dev'],before['ino']) and stamp(path)==before,'checkpoint lock replaced')
            identities.append((path,before,fd))
        def recheck():
            for path,before,fd in identities:
                s=os.fstat(fd)
                require((s.st_dev,s.st_ino)==(before['dev'],before['ino']) and stamp(path)==before,'held checkpoint lock replaced')
        no_owner();recheck();yield recheck
    finally:
        for fd in reversed(held):os.close(fd)

def inventory(*,hash_blobs=True):
    guards,audit=closed_guards();files={};dirs={}
    for cid in IDS:
        tree=CHECKPOINTS/cid;dirs[rel(tree)]=directory(tree)
        manifest_path=tree/'manifest.json';manifest=read(manifest_path)
        require(pin(manifest_path)['sha256']==audit['artifact_sha256'][rel(manifest_path)]['sha256'],'audited manifest changed')
        require(manifest['checkpoint_id']==cid and manifest['label']=='experimental-postreply-front'
                and manifest['contract']=='v1.2+p198' and len(manifest['blobs'])==128,'native checkpoint identity changed')
        expected={'manifest.json':None,'fields.tsv':None,'tokens.bin':dict(bytes=manifest['token_state']['length']*4,
                   sha256=manifest['token_state']['tokens_sha256'])}
        for blob in manifest['blobs']:
            name=blob['name'];require(isinstance(name,str) and re.fullmatch(r'[A-Za-z0-9_.-]+',name),'invalid blob name')
            key=name+'.bin';require(key not in expected,'duplicate native blob');expected[key]=blob
        require({p.name for p in tree.iterdir()}==set(expected),'checkpoint file set changed')
        for name,declaration in expected.items():
            path=tree/name;s=stamp(path)
            entry=pin(path) if hash_blobs or declaration is None else dict(stamp=s,sha256=declaration['sha256'])
            if declaration is not None:
                require(entry['stamp']['bytes']==declaration['bytes'] and entry['sha256']==declaration['sha256'],
                        'native manifest extent/hash mismatch: '+name)
            files[rel(path)]=dict(**entry,archive_member='checkpoints/'+cid+'/'+name,
                tensor_prune_candidate=name.startswith('blk.') and name.endswith('.bin'))
    require(len(files)==262 and sum(v['stamp']['bytes'] for v in files.values())==TOTAL_BYTES,'fixed inventory changed')
    candidates=[n for n,v in files.items() if v['tensor_prune_candidate']]
    require(len(candidates)==242 and sum(files[n]['stamp']['bytes'] for n in candidates)==TENSOR_BYTES,'fixed tensor scope changed')
    tracked=set(subprocess.check_output(['git','ls-files','-z','--',rel(PACKET)],cwd=ROOT).decode().split('\0'))
    return dict(files=files,directories=dirs,guards=guards,blob_hashes_verified=hash_blobs,
                tracked_files=sorted(set(files)&tracked),tracked_tensor_candidates=sorted(set(candidates)&tracked))

def verify_members(archive,originals):
    expected={v['archive_member']:v for v in originals['files'].values()};verified={};dirs=set()
    wanted_dirs={'checkpoints'}|{'checkpoints/'+cid for cid in IDS}
    for member in archive:
        require(member.name not in verified and member.name not in dirs,'duplicate archive member')
        if member.isdir():require(member.name in wanted_dirs,'unexpected archive directory');dirs.add(member.name);continue
        require(member.isfile() and member.name in expected,'unexpected member/type')
        row=expected[member.name];require(member.size==row['stamp']['bytes'],'archive extent mismatch')
        with archive.extractfile(member) as stream:digest=U.sha_stream(stream)
        require(digest==row['sha256'],'archive member hash mismatch');verified[member.name]=digest
    require(set(verified)==set(expected) and dirs==wanted_dirs,'incomplete archive')
    return verified

@contextmanager
def verified_archive(originals):
    """Retain the exact recovery inode through the caller's destructive phase."""
    before=pin(ARCHIVE);parent=directory(ARCHIVE.parent)
    fd=os.open(ARCHIVE,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
    with os.fdopen(fd,'rb') as stream:
        def recheck():
            s=os.fstat(stream.fileno())
            require((s.st_dev,s.st_ino)==(before['stamp']['dev'],before['stamp']['ino'])
                    and stamp(ARCHIVE)==before['stamp'] and directory(ARCHIVE.parent)==parent,'held archive changed')
        recheck()
        with tarfile.open(fileobj=stream,mode='r:') as archive:verified=verify_members(archive,originals)
        recheck();stream.seek(0)
        require(U.sha_stream(stream)==before['sha256'],'archive changed during readback')
        # Caller performs its final check inside receipt failure handling, before
        # publishing passed. Teardown must not reject after a success receipt.
        recheck();yield before,verified,recheck

def verify_archive(originals):
    with verified_archive(originals) as (before,verified,recheck):return before,verified

def copy_verify():
    require(not any(os.path.lexists(p) for p in (ARCHIVE,SIDECAR,RECEIPT,PRUNE_RECEIPT,MARKER)),
            'one-shot destination exists; preserve and review')
    placement();mount=storage()
    with locked() as check_locks,ExitStack() as retained:
        before=inventory();require(not before['tracked_tensor_candidates'],'tracked tensor candidate refused')
        row=dict(schema='p199-closed-checkpoint-archive-v1',passed=False,created_utc=utc(),archive=str(ARCHIVE),
                 originals=before,storage=mount,deleted_files=0,phase='copy-in-progress')
        write(RECEIPT,row)
        try:
            with ARCHIVE.open('xb') as raw:
                with tarfile.open(fileobj=raw,mode='w',format=tarfile.PAX_FORMAT) as archive:
                    for name in ['checkpoints',*('checkpoints/'+cid for cid in IDS)]:
                        info=tarfile.TarInfo(name);info.type=tarfile.DIRTYPE;info.mode=0o700;archive.addfile(info)
                    for name,entry in sorted(before['files'].items()):
                        source=ROOT/name
                        require(directory(source.parent)==before['directories'][rel(source.parent)],'checkpoint directory replaced')
                        require(stamp(source)==entry['stamp'],'source changed before copy')
                        fd=os.open(source,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC)
                        with os.fdopen(fd,'rb') as stream:
                            s=os.fstat(stream.fileno());require((s.st_dev,s.st_ino)==(entry['stamp']['dev'],entry['stamp']['ino']),'source replaced')
                            info=tarfile.TarInfo(entry['archive_member']);info.size=s.st_size;info.mode=0o600
                            archive.addfile(info,stream)
                        require(stamp(source)==entry['stamp'],'source changed while copying')
                raw.flush();os.fsync(raw.fileno())
            sync_parent(ARCHIVE)
            archive_pin,members,check_archive=retained.enter_context(verified_archive(before))
            require(inventory()==before,'originals or guards changed after readback');no_owner()
            check_locks();check_archive()
            require(storage()['parent']==mount['parent'],'external storage identity changed')
            with SIDECAR.open('x') as side:
                side.write(archive_pin['sha256']+'  '+ARCHIVE.name+'\n');side.flush();os.fsync(side.fileno())
            sync_parent(SIDECAR)
            check_locks();check_archive()
            row.update(passed=True,phase='verified-copy-only',verified_utc=utc(),archive_pin=archive_pin,
                       verified_member_sha256=members,original_files_unchanged=True,
                       candidate_files=242,candidate_bytes=TENSOR_BYTES,restore_map={n:v['archive_member'] for n,v in before['files'].items()})
        except BaseException as error:
            row.update(error=str(error),phase='failed-copy-preserved',passed=False);raise
        finally:write(RECEIPT,row,'w')
    return row

def placement():
    require(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32)),
            'nice19/helper cores required')

def main():
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--plan',action='store_true');mode.add_argument('--copy-verify',action='store_true');args=parser.parse_args();placement()
    if args.plan:
        row=dict(read_only=True,blob_hashes_verified=False,archive=str(ARCHIVE),storage=storage(),inventory=inventory(hash_blobs=False),
                 copy_requires='Current inactive owner proof and exclusive existing native locks, complete blob hashing, full tar readback and original rehash')
    else:row=copy_verify();row={k:row[k] for k in ('passed','phase','archive','candidate_bytes','deleted_files')}
    print(json.dumps(row,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
