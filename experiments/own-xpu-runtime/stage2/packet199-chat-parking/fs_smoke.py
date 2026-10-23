#!/usr/bin/env python3
"""UNUSED alternative: root selected private local ext4; do not run this probe.
Prepared tiny filesystem probe retained as planning evidence; no execution occurred."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path

MOUNT=Path('/mnt/usb-models')
OUTPUT=MOUNT/'packet199-fs-smoke-20261023-a'


def info(path):
    st=path.stat()
    return dict(path=str(path),uid=st.st_uid,gid=st.st_gid,mode=oct(st.st_mode&0o7777),st_dev=st.st_dev,inode=st.st_ino)


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--plan',action='store_true');m.add_argument('--run-fs-smoke',action='store_true');args=p.parse_args()
    assert MOUNT.resolve(strict=True)==MOUNT and not os.path.lexists(OUTPUT),'real mount and fresh fixed test directory required'
    row=dict(passed=False,device_executed=False,native_executed=False,output=str(OUTPUT),mount=info(MOUNT),
             script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),required_uid=os.getuid(),required_mode='0o700',
             operations=['exclusive mkdir0700 and actualuid/mode check','shared/exclusive flock contention','smallfilefsync','atomic rename and directoryfsync'])
    if args.plan:row.update(read_only=True);print(json.dumps(row,indent=2));return
    assert os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
    directory_fd=None
    try:
        OUTPUT.mkdir(mode=0o700)
        row['created_directory']=info(OUTPUT)
        assert OUTPUT.stat().st_uid==os.getuid() and OUTPUT.stat().st_mode&0o7777==0o700,'filesystem did not provide actual owner-private0700; no relaxation'
        assert OUTPUT.stat().st_dev==MOUNT.stat().st_dev,'unexpected filesystem'
        directory_fd=os.open(OUTPUT,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        with (OUTPUT/'checkpoint.lock').open('xb') as one,(OUTPUT/'checkpoint.lock').open('rb') as two:
            fcntl.flock(one,fcntl.LOCK_SH|fcntl.LOCK_NB)
            try:fcntl.flock(two,fcntl.LOCK_EX|fcntl.LOCK_NB)
            except BlockingIOError:row['lock_contention_refused']=True
            else:raise RuntimeError('exclusive lock bypassed shared lock')
            fcntl.flock(one,fcntl.LOCK_UN);fcntl.flock(two,fcntl.LOCK_EX|fcntl.LOCK_NB)
            row['exclusive_after_release']=True
        payload=b'packet199 filesystem smoke only; no model/device data\n'
        with (OUTPUT/'manifest.tmp').open('xb') as f:f.write(payload);f.flush();os.fsync(f.fileno())
        (OUTPUT/'manifest.tmp').rename(OUTPUT/'manifest.test');os.fsync(directory_fd)
        assert (OUTPUT/'manifest.test').read_bytes()==payload
        row.update(passed=True,file_and_directory_fsync=True,atomic_rename_readback=True)
        with (OUTPUT/'receipt.json').open('x') as f:f.write(json.dumps(row,indent=2)+'\n');f.flush();os.fsync(f.fileno())
        os.fsync(directory_fd)
    except Exception as e:
        row['error']=str(e);row['no_cleanup_or_mount_change']=True
    finally:
        if directory_fd is not None:os.close(directory_fd)
    print(json.dumps(row,indent=2))
    if not row['passed']:raise SystemExit(1)


if __name__=='__main__':main()
