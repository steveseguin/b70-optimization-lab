"""Read-only admission to an existing continuous coordinator one-card hold."""
import hashlib,json,stat
from datetime import datetime
from pathlib import Path
from build_engine import P
QUEUE=P.parents[1]/'ops/lane-queue'
PAUSE=QUEUE/'PAUSE-B'
EVENTS=QUEUE/'events-A.jsonl'
JOB='packet58af-measure-A'

def require(good,message):
    if not good:raise ValueError(message)

def pause_identity(path=None):
    path=PAUSE if path is None else path
    try:
        before=path.lstat()
        require(stat.S_ISREG(before.st_mode),'PAUSE-B must be a regular file, not a symlink')
        require(before.st_size<=65536,'PAUSE-B text exceeds 64 KiB')
        raw=path.read_bytes();after=path.lstat()
    except FileNotFoundError as error:
        raise ValueError('existing coordinator PAUSE-B required; no standalone hold') from error
    fields=lambda s:(s.st_dev,s.st_ino,s.st_mtime_ns,s.st_ctime_ns)
    require(fields(before)==fields(after),'PAUSE-B changed while reading')
    text=raw.decode().lower().replace('_','-')
    require(('one-card' in text or 'one card' in text) and ('whole-host' in text or 'whole host' in text) and 'hold' in text,
            'PAUSE-B must name a one-card whole-host hold')
    require('58ab' in text,'packet58ab hold required')
    return dict(device=after.st_dev,inode=after.st_ino,mtime_ns=after.st_mtime_ns,ctime_ns=after.st_ctime_ns,
                text=raw.decode(),sha256=hashlib.sha256(raw).hexdigest())

def job_start(path=None):
    path=EVENTS if path is None else path
    latest=None
    with path.open() as stream:
        for line in stream:
            row=json.loads(line)
            if row.get('event')=='START' and row.get('lane')=='A':latest=row
            elif row.get('name')==JOB and (row.get('event','').startswith(('DONE','FAIL','REFUSED','REPORT-FAILED')) or row.get('event')=='EXIT'):
                latest=None
    require(latest is not None and latest.get('name')==JOB,'current lane-A START must name this job')
    stamp=datetime.fromisoformat(latest['utc'].replace('Z','+00:00'))
    require(stamp.tzinfo is not None,'START needs UTC timezone')
    ns=int(stamp.timestamp())*1_000_000_000+stamp.microsecond*1000
    return dict(event=latest,started_utc_ns=ns)

def verify():
    pause=pause_identity();start=job_start()
    require(pause['mtime_ns']<start['started_utc_ns'] and pause['ctime_ns']<start['started_utc_ns'],
            'PAUSE-B must predate this job START; no new or replaced hold')
    require(pause_identity()==pause,'hold changed during admission')
    return dict(passed=True,same_hold_required=True,standalone_hold_allowed=False,pause=pause,
                lanequeue_start=start,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip())

def recheck(receipt):
    require(pause_identity()==receipt['pause'],'continuous coordinator hold changed')
    require(job_start()==receipt['lanequeue_start'],'current lanequeue START changed')
