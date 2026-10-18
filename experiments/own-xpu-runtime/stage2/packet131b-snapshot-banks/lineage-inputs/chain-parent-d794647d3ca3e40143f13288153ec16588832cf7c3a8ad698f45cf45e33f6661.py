#!/usr/bin/env python3
"""Independent CPU-only socket/process controller review tests; no device binary."""
import argparse
import json
import mmap
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import pipeline as p

STUB = r'''
import json,os,select,socket,struct,sys,time
from pathlib import Path
rank,channel,stop_fd=int(sys.argv[1]),int(sys.argv[2]),int(sys.argv[3])
out=Path(sys.argv[4]);mode=sys.argv[5]
sock=socket.socket(fileno=channel)
req=struct.Struct("<8i");rep=struct.Struct("<8i4d")
def response(seq):
    data=rep.pack(0,3,0,0,seq,rank,0,0,0.,0.,0.,0.)
    for begin in range(0,len(data),3):
        sock.sendall(data[begin:begin+3]);time.sleep(.001)
def receipt(passed=True):
    (out/"receipt.json").write_text(json.dumps(dict(passed=passed,rank=rank,teardown=[dict(safe_to_exit=True,in_flight=0,live_bytes=0)])))
response(0)
while True:
    data=b""
    while len(data)<req.size:
        ready,_,_=select.select([sock,stop_fd],[],[],.1)
        if stop_fd in ready:receipt(False);sys.exit(1)
        if sock in ready:
            chunk=sock.recv(req.size-len(data))
            if not chunk:receipt(False);sys.exit(1)
            data+=chunk
    op,token,position,fixture,spec,seq,_,_=req.unpack(data)
    if op==5:
        if mode=="delay_finish":time.sleep(.15)
        receipt(mode!="bad_receipt");sys.exit(0)
    if op==7:receipt(False);sys.exit(1)
    if op==8:
        while True:
            ready,_,_=select.select([stop_fd],[],[],.1)
            if ready:receipt(False);sys.exit(1)
    if mode=="short_reply":sock.sendall(rep.pack(0,0,0,0,seq,rank,0,0,0,0,0,0)[:5]);receipt(False);sys.exit(1)
    response(seq+1 if mode=="bad_sequence" else seq)
'''

def transport(out,modes=("normal","normal"),timeout=.4):
    """Real child processes and socketpairs, host-only protocol stub backend."""
    out.mkdir()
    t=p.Transport.__new__(p.Transport)
    t.a=SimpleNamespace(seconds=20,wait_seconds=timeout)
    t.out=out;t.device=False;t.check=lambda:None
    t.children=[];t.sockets=[];t.logs=[];t.seq=[0,0];t.pending=[False,False];t.started=[0.,0.];t.commands=[{},{}]
    t.metrics=[dict(busy_ms=0.,handover_ms=0.,calls=0,gpu_ms=0.) for _ in range(2)]
    t.trace=[];t.stop_sent=False;t.retained=[];t.failure_hook=lambda reason:None;t.start_time=time.monotonic()
    # Compatibility with idempotent close/expected-exit fields added after review.
    t.closed=False;t.finishing=set();t.expected_exits=set();t.last_complete=[0.,0.]
    t.shared_path=out/"shared.bin"
    fd=os.open(t.shared_path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600);os.ftruncate(fd,p.SHARED)
    t.mapping=mmap.mmap(fd,p.SHARED);os.close(fd)
    t.stop_read,t.stop_write=os.pipe()
    for rank in range(2):
        parent,child=socket.socketpair();parent.setblocking(False);t.sockets.append(parent)
        dest=out/f"rank{rank}";dest.mkdir()
        log=(out/f"rank{rank}.log").open("w");t.logs.append(log)
        cmd=["nice","-n","19","ionice","-c","3",sys.executable,"-B","-c",STUB,str(rank),str(child.fileno()),str(t.stop_read),str(dest),modes[rank]]
        proc=subprocess.Popen(cmd,pass_fds=(child.fileno(),t.stop_read),stdout=log,stderr=subprocess.STDOUT,env={"PATH":"/usr/bin:/bin","OMP_NUM_THREADS":"2"})
        t.children.append(proc);child.close()
    for rank in range(2):t.receive(rank,2,ready=True)
    return t

def cleanup(t):
    # No hard kills, including test cleanup. All stubs poll this inherited pipe.
    try:t.stop("review test cleanup")
    except OSError:pass
    for child in t.children:
        try:child.wait(timeout=3)
        except subprocess.TimeoutExpired:raise AssertionError("stub failed cooperative stop; retained for owner")
    for sock in t.sockets:sock.close()
    for log in t.logs:log.close()
    try:t.mapping.close()
    except ValueError:pass
    for fd in (t.stop_read,t.stop_write):
        try:os.close(fd)
        except OSError:pass

def expect_failure(fn):
    try:fn()
    except (ValueError,ConnectionError,OSError):return
    raise AssertionError("failure was not detected")

def partial_reply(out):
    t=transport(out)
    try:
        result=t.call(0,p.DUMP)
        assert result["token"]==3 and not t.pending[0]
        assert t.seq[0]==1
    finally:cleanup(t)

def short_reply(out):
    t=transport(out,("short_reply","normal"))
    try:
        expect_failure(lambda:t.call(0,p.DUMP))
        t.stop("short-frame failure")
        assert (out/"failure-before-teardown.json").exists()
        t.close(False)
        assert not t.retained and t.children[1].returncode==1
    finally:cleanup(t)

def failed_rank(out):
    t=transport(out)
    try:
        expect_failure(lambda:t.call(0,p.FAIL))
        t.stop("rank failed")
        t.close(False)
        assert all(c.returncode==1 for c in t.children)
        assert json.loads((out/"ownership.json").read_text())["signals_sent"]==0
    finally:cleanup(t)

def stalled_rank(out):
    t=transport(out,timeout=.15)
    try:
        start=time.monotonic()
        expect_failure(lambda:t.call(0,p.STALL))
        assert time.monotonic()-start<2
        t.stop("rank stalled")
        t.close(False)
        assert all(c.returncode==1 for c in t.children)
    finally:cleanup(t)

def stop_both_idle(out):
    t=transport(out)
    try:
        hooks=[];t.failure_hook=lambda reason:hooks.append(reason)
        t.stop("idle stop");t.stop("ignored duplicate")
        assert hooks==["idle stop"]
        t.close(False)
        assert all(c.returncode==1 for c in t.children)
        assert json.loads((out/"failure-before-teardown.json").read_text())["reason"]=="idle stop"
    finally:cleanup(t)

def finish_exit_race(out):
    t=transport(out)
    original=t.io
    def forced(rank,payload=None,timeout=None):
        result=original(rank,payload,timeout)
        if rank==0 and payload and p.REQUEST.unpack(payload)[0]==p.FINISH:
            t.children[0].wait(timeout=2)
        return result
    t.io=forced
    try:
        t.close(True)
        assert all(c.returncode==0 for c in t.children)
    finally:cleanup(t)

def failed_teardown_idempotent(out):
    t=transport(out,("bad_receipt","normal"))
    try:
        expect_failure(lambda:t.close(True))
        # run() invokes these on a close(True) validation failure. Must not EBADF.
        t.stop("failed receipt after exits")
        t.close(False)
    finally:cleanup(t)

def wrong_sequence(out):
    t=transport(out,("bad_sequence","normal"))
    try:
        expect_failure(lambda:t.call(0,p.DUMP))
        t.stop("invalid reply sequence");t.close(False)
        assert all(c.returncode==1 for c in t.children)
    finally:cleanup(t)

def stop_pipe_closure(out):
    t=transport(out)
    try:
        os.close(t.stop_write);t.closed=True
        # EOF is persistently readable even though no stop byte was written.
        for child in t.children:child.wait(timeout=2)
        assert all(c.returncode==1 for c in t.children)
    finally:cleanup(t)

def watcher_during_drain(out):
    t=transport(out,("delay_finish","delay_finish"))
    hooks=[];t.failure_hook=lambda reason:hooks.append(str(reason))
    sent=[];original=t.io
    def record_io(rank,payload=None,timeout=None):
        result=original(rank,payload,timeout)
        if payload and p.REQUEST.unpack(payload)[0]==p.FINISH:sent.append(rank)
        return result
    t.io=record_io
    def watcher():
        if len(sent)==2:raise ValueError("injected fault during native drain")
    try:
        t.check=watcher
        expect_failure(lambda:t.close(True))
        assert hooks==["injected fault during native drain"]
        assert not t.retained
        assert json.loads((out/"ownership.json").read_text())["signals_sent"]==0
    finally:cleanup(t)

def producer_slot_guard(out):
    t=transport(out)
    try:
        t.stream_bytes=16;t.mapping[:16]=b"A"*16
        t.pending[1]=True
        expect_failure(t.handover)
        t.pending[1]=False;t.handover()
        assert t.mapping[p.SLOT:p.SLOT+16]==b"A"*16
    finally:cleanup(t)

def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    root=Path(tempfile.mkdtemp(prefix="review-controller-",dir=Path(__file__).parent/"build"))
    rows=[]
    try:
        for fn in (partial_reply,short_reply,failed_rank,stalled_rank,stop_both_idle,finish_exit_race,failed_teardown_idempotent,wrong_sequence,stop_pipe_closure,watcher_during_drain,producer_slot_guard):
            start=time.monotonic()
            try:fn(root/fn.__name__);row=dict(test=fn.__name__,passed=True)
            except Exception as exc:row=dict(test=fn.__name__,passed=False,error=repr(exc))
            row["seconds"]=time.monotonic()-start;rows.append(row);print(json.dumps(row),flush=True)
        a.output.write_text(json.dumps(dict(passed=all(r["passed"] for r in rows),device_executed=False,tests=rows),indent=2)+"\n")
    finally:shutil.rmtree(root)
    return 0 if all(r["passed"] for r in rows) else 1
if __name__=="__main__":raise SystemExit(main())
