#!/usr/bin/env python3
"""Mock-only build inventory deletion race checks; no ranks or filesystem scan."""
import errno,hashlib,json,os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import storage

def main():
    assert os.getpriority(os.PRIO_PROCESS,0)==19
    root=Mock();live=Mock();live.is_file.return_value=True;live.is_symlink.return_value=False;live.stat.return_value=SimpleNamespace(st_size=37)
    vanished=Mock();vanished.is_file.return_value=True;vanished.is_symlink.return_value=False;vanished.stat.side_effect=FileNotFoundError(errno.ENOENT,'concurrent deletion')
    early=Mock();early.is_file.side_effect=FileNotFoundError(errno.ENOENT,'deleted before type check')
    link=Mock();link.is_file.return_value=True;link.is_symlink.return_value=True
    directory=Mock();directory.is_file.return_value=False
    root.rglob.return_value=[live,vanished,early,link,directory]
    assert storage.build_size(root)==37
    checks=['vanished stat/type-check members skipped while surviving bytes counted and symlink excluded']
    for error in [PermissionError(errno.EACCES,'denied'),OSError(errno.EIO,'io error')]:
        bad=Mock();bad.is_file.return_value=True;bad.is_symlink.return_value=False;bad.stat.side_effect=error
        root.rglob.return_value=[bad]
        try:storage.build_size(root)
        except type(error) as observed:assert observed is error
        else:raise AssertionError('unexpected I/O error swallowed')
        checks.append(type(error).__name__+' propagated')
    packet=Path(__file__).resolve().parent
    receipt=dict(passed=True,device_executed=False,native_ranks_executed=False,mocked_only=True,checks=checks,source_sha256={n:hashlib.sha256((packet/n).read_bytes()).hexdigest() for n in ['storage.py','test_storage_race.py']})
    (packet/'storage-race-gates.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(dict(passed=True,checks=len(checks))))
if __name__=='__main__':main()
