"""Refuse standalone admission; read only the coordinator's continuous pause.

The coordinator owns batching. This guard never creates/removes a hold, pauses
queues or grants device permission. Existing admission still checks all clients.
"""
import json
from pathlib import Path
from build_engine import P,ROOT,sha
QUEUE=P.parents[1]/'ops/lane-queue'
P58X=P.parent/'packet58x-cache-capacity'
PAUSE=QUEUE/'PAUSE-B'

def require(good,message):
    if not good:raise ValueError(message)

def pause_identity(path=PAUSE):
    require(path.is_file() and not path.is_symlink(),'58y requires the existing continuous 58x PAUSE-B; no standalone hold')
    st=path.stat()
    return dict(device=st.st_dev,inode=st.st_ino,mtime_ns=st.st_mtime_ns,ctime_ns=st.st_ctime_ns)

def verify():
    pause=pause_identity();boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    contract=json.loads((P/'batch-contract.json').read_text());pins={};starts=[]
    for name,digest in contract['predecessor_proposals'].items():
        require(sha(ROOT/name)==digest,'58x proposal changed; replan the batch')
    build_sha=sha(P58X/'build-receipt.json');previous_end=0
    for arm in ('smoke','max'):
        root=P58X/'evidence/card0-capacity-a'/arm
        q=json.loads((root/'queue.json').read_text())
        require(q.get('passed') is True and q.get('completed')==['K1a','K1b','WSCREEN'] and q.get('running') is None,'58x prerequisite did not complete cleanly')
        for stage in ('K1a','K1b','WSCREEN'):
            f=root/stage/'window.json';row=json.loads(f.read_text())
            require(row.get('passed') is True and row.get('device_executed') is True and row.get('child_still_running') is False and row.get('stop_reasons')==[], '58x window failed or owner remains')
            require(row['boot_id']==boot and row['build_receipt_sha256']==build_sha,'58x prerequisite identity changed')
            require(type(row['started_utc_ns']) is int and type(row.get('finished_utc_ns')) is int and previous_end<=row['started_utc_ns']<row['finished_utc_ns'],'58x smoke/bracket windows are out of order')
            previous_end=row['finished_utc_ns']
            starts.append(row['started_utc_ns']);pins[str(f.relative_to(ROOT))]=sha(f)
        pins[str((root/'queue.json').relative_to(ROOT))]=sha(root/'queue.json')
    require(pause['mtime_ns']<=min(starts) and pause['ctime_ns']<=min(starts),'PAUSE-B was recreated/changed after 58x began; same hold not established')
    return dict(passed=True,same_hold_required=True,standalone_hold_allowed=False,
                pause=pause,boot_id=boot,predecessor_receipts=pins)

def recheck(receipt):
    require(pause_identity()==receipt['pause'],'58x/58y continuous hold changed')
