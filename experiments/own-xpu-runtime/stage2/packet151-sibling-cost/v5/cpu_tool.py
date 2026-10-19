"""Run frozen CPU plan/loader tools with pause-aware subprocess deadlines."""
import sys,runpy,resource
from pathlib import Path
import freeze_safe
freeze_safe.install()
resource.setrlimit(resource.RLIMIT_DATA,(4*1024**3,)*2)
path=Path(sys.argv[1]).resolve();sys.argv=sys.argv[1:]
assert path.name in ('lanequeue.py','launch_env.py')
if path.name=='lanequeue.py':assert sys.argv[1]=='plan' and '--directory' in sys.argv
sys.path.insert(0,str(path.parent))
if path.name=='launch_env.py':
 sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'ops'))
 import entry_sandbox
runpy.run_path(str(path),run_name='__main__')
