#!/usr/bin/env python3
"""CPU-only mocked storage failure regression; no ranks or device calls."""
import argparse, errno, hashlib, json, os, tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
import pipeline

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    root=Path(__file__).resolve().parent
    rows=[]
    with tempfile.TemporaryDirectory(prefix='storage-review-',dir=root/'build') as scratch:
        for fail_hook,fail_record in ((False,True),(True,False),(True,True)):
            t=pipeline.Transport.__new__(pipeline.Transport)
            t.out=Path(scratch);t.stop_sent=False;t.closed=False;t.check=lambda:None
            t.children=[SimpleNamespace(pid=123,poll=lambda:1),SimpleNamespace(pid=124,poll=lambda:1)]
            t.mapping=Mock();t.sockets=[Mock(),Mock()];t.logs=[Mock(),Mock()]
            t.shared_path=t.out/'shared.bin';t.shared_path.write_bytes(b'')
            t.stop_read,t.stop_write=os.pipe();t.retained=[]
            events=[]
            def hook(reason):
                events.append('hook')
                if fail_hook:raise OSError(errno.ENOSPC,'injected hook failure')
            def save(path,value):
                events.append('receipt')
                if fail_record:raise OSError(errno.ENOSPC,'injected receipt failure')
            t.failure_hook=hook
            try:
                with patch.object(pipeline,'save',save):
                    t.stop('injected rank failure')
                    assert os.read(t.stop_read,1)==b'!'
                    assert events==['hook','receipt']
                    t.stop('duplicate');assert events==['hook','receipt']
                    try:t.close(False)
                    except OSError:
                        assert fail_record
                    assert t.closed and not t.retained
                    t.mapping.close.assert_called_once()
                    for handle in t.sockets+t.logs:handle.close.assert_called_once()
                rows.append(dict(hook_failure=fail_hook,receipt_failure=fail_record,passed=True,stop_byte_observed=True,closed_after_write_failure=True))
            finally:
                for fd in (t.stop_read,t.stop_write):
                    try:os.close(fd)
                    except OSError:pass
    names=['pipeline.py','suite.py','rank.hpp','test_failure_storage.py']
    record=dict(passed=True,device_executed=False,ranks_launched=False,gates=len(rows),cases=rows,
                source_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in names},
                scope='Python stop and drain mock regressions; C++ failure catch inspected only, not compiled by this test')
    args.output.write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(dict(passed=True,gates=len(rows))))
if __name__=='__main__':main()
