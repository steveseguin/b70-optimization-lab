#!/usr/bin/env python3
"""Window failure/storage regression, mocked owners only; never device execution."""
import argparse, errno, json, os, tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import window as w
import storage

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    storage.admit(25_000_000)
    rows=[]
    with tempfile.TemporaryDirectory(prefix='window-storage-',dir=w.B) as scratch:
        root=Path(scratch)
        # A log write failure must not erase the fresh-fault observation.
        watch_obj=w.Watch.__new__(w.Watch);watch_obj.last=0.;watch_obj.cursor='old';watch_obj.out=root/'absent';watch_obj.new_gpu_fault=False
        latches=[];watch_obj.latch=lambda reason:latches.append(reason)
        with patch.object(w,'journal',lambda cursor:('Fault response\\n','new')):
            try:watch_obj.poll_kernel()
            except OSError:pass
        assert watch_obj.new_gpu_fault and latches==['GPU fault signature']
        rows.append(dict(name='new-kernel-fault-survives-log-write-failure',passed=True))
        stop_observed=[]
        class Child:
            pid=987654;returncode=None
            def __init__(self,fd):self.fd=fd;os.set_blocking(fd,False)
            def poll(self):
                if self.returncode is not None:return self.returncode
                try:
                    if os.read(self.fd,1)==b'!':stop_observed.append(True);self.returncode=0
                except BlockingIOError:pass
                return self.returncode
        def fail(*args,**kwargs):raise OSError(errno.ENOSPC,'injected storage/hook failure')
        watch=SimpleNamespace(check=lambda:None,latch=fail,mark_launched=lambda pid:None)
        args=SimpleNamespace(window='K1a',card=0,seconds=None,dispatch=None)
        with patch.object(w,'admit',lambda n,**kw:None),patch.object(w,'ldd_preflight',lambda p:None),patch.object(w,'sha',lambda p:'mock'),patch.object(w,'save',fail),patch.object(w.subprocess,'Popen',lambda *a,**k:Child(k['pass_fds'][0])):
            try:w.run_fixtures(args,root,{},watch)
            except OSError:pass
            else:raise AssertionError('fixture failure missing')
        assert stop_observed==[True]
        rows.append(dict(name='fixture-receipt-and-latch-failure-still-stops',passed=True))
        actions=[]
        class BrokenTransport:
            def __init__(self,*args):self.stop_write=1;raise ValueError('injected constructor failure')
            def stop(self,error):actions.append('stop')
            def close(self,success):assert success is False;actions.append('drain')
        args=SimpleNamespace(device=False)
        with patch.object(w,'admit',lambda n,**kw:None),patch.object(w,'save',fail),patch.object(w,'Transport',BrokenTransport):
            try:w.concurrency_canary(args,root,{},watch)
            except ValueError:pass
            else:raise AssertionError('canary failure missing')
        assert actions==['stop','drain']
        rows.append(dict(name='canary-receipt-and-latch-failure-still-drains',passed=True))
        data=root/'retention';data.mkdir();run=data/'run0';run.mkdir();blob=run/'output.bin';blob.write_bytes(b'x'*20_000_001)
        digest=w.stream_hash(blob);w.save(run/'receipt.json',dict(passed=True,schema='packet26.fixtures.v1',output_sha256=digest))
        dispatch=data/'dispatch.json';dispatch.write_text('{}')
        launch=dict(directory='run0',binary='k2-fixtures',binary_sha256='b'*64,argv=['sealed/k2-fixtures','--output',str(run),'--dispatch',str(dispatch)])
        w.save(data/'children.json',dict(entries=[launch]));record=dict(artifacts_sha256={'device/k2-fixtures':'b'*64})
        (data/'events.jsonl').write_text('{"event":1}\n');(data/'rank.log').write_text('diagnostic\n')
        w.compress_evidence(data,record)
        assert not blob.exists() and not (data/'events.jsonl').exists() and not (run/'output.bin.gz').exists()
        assert w.retained_hash(data,'run0/output.bin',record)==digest
        assert len(record['retained_artifacts'])==3
        item=record['retained_artifacts']['run0/output.bin'];assert item['disposition']=='sha256-only' and item['launch_entry']==launch
        assert item['native_receipt_sha256']==w.sha(run/'receipt.json')
        rows.append(dict(name='oversized-fixture-native-hash-provenance-before-delete-no-duplicate',passed=True))
        good=(run/'receipt.json').read_bytes();(run/'receipt.json').write_text('{}')
        try:w.retained_hash(data,'run0/output.bin',record)
        except ValueError:pass
        else:raise AssertionError('tampered native receipt accepted')
        (run/'receipt.json').write_bytes(good)
        item['uncompressed_sha256']='0'*64
        try:w.retained_hash(data,'run0/output.bin',record)
        except ValueError:pass
        else:raise AssertionError('unverified arbitrary digest accepted')
        item['uncompressed_sha256']=digest;item['native_receipt_path']='../outside.json'
        try:w.retained_hash(data,'run0/output.bin',record)
        except ValueError:pass
        else:raise AssertionError('fixture provenance path escape accepted')
        item['native_receipt_path']='run0/receipt.json'
        rows.append(dict(name='native-provenance-digest-and-path-tampering-refused',passed=True))
        packed=data/record['retained_artifacts']['events.jsonl']['path'];packed.write_bytes(packed.read_bytes()+b'bad')
        try:w.retained_hash(data,'events.jsonl',record)
        except ValueError:pass
        else:raise AssertionError('tampered compressed event log accepted')
        rows.append(dict(name='logs-still-losslessly-compressed-and-authenticated',passed=True))
        blob.write_bytes(b'x'*20_000_001)
        with patch.object(w,'save',fail):
            try:w.compress_evidence(data,dict(artifacts_sha256={'device/k2-fixtures':'b'*64}))
            except OSError:pass
            else:raise AssertionError('retention mapping write failure hidden')
        assert blob.exists(),'raw fixture deleted before durable provenance';blob.unlink()
        rows.append(dict(name='provenance-write-failure-preserves-raw-fixture-no-latch',passed=True))
        with patch.object(w,'admit') as admit:
            w.admit_output(w.B/'new',123);assert admit.call_args.kwargs=={'build_extra':123}
            w.admit_output(w.P/'receipts-unique/K2',456);assert admit.call_args.args==(456,) and admit.call_args.kwargs=={'build_extra':0}
        assert w.output_path(w.P/'receipts-unique/K2')==w.P/'receipts-unique/K2'
        try:w.output_path(w.P.parent/'not-packet40')
        except ValueError:pass
        else:raise AssertionError('outside packet output accepted')
        assert w.projected_write_bytes('K2')>=979339200+60*1600*12292+119337064
        assert w.watchdog('K2')>=4*(w.CONFIG['K2'][0]+17)
        rows.append(dict(name='packet-contained-output-root-reserve-build-budget-and-K2-bound',passed=True))
    import hashlib
    names=['window.py','test_window_storage.py']
    a.output.write_text(json.dumps(dict(passed=True,device_executed=False,ranks_launched=False,gates=len(rows),cases=rows,source_sha256={n:hashlib.sha256((w.P/n).read_bytes()).hexdigest() for n in names}),indent=2)+'\n')
    print(json.dumps(dict(passed=True,gates=len(rows))))
if __name__=='__main__':main()
