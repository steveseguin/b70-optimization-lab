"""Executed by the future admitted user service, never by CPU build gates."""
import json,os,sys
from pathlib import Path
expected=int(sys.argv[1]);actual=os.getpriority(os.PRIO_PROCESS,0)
Path(sys.argv[2]).write_text(json.dumps(dict(pid=os.getpid(),requested_nice=expected,actual_nice=actual,passed=actual==expected))+"\n")
if actual!=expected:raise SystemExit("native priority mismatch; refusing measurement")
os.execv(sys.argv[3],sys.argv[3:])
