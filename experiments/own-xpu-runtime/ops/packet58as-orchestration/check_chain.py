"""CPU-only chain argv, temporary lanequeue admission and submission checks."""
import ast,hashlib,json,resource,subprocess,sys,tempfile
from pathlib import Path
resource.setrlimit(resource.RLIMIT_AS,(2_000_000_000,2_000_000_000))
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait'
sys.path.insert(0,str(P))
import queue_runner as Q, suite_driver as D, composition as C
from launch_env import library_path
from types import SimpleNamespace

def sha(p):
 with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
commands=Q.commands(P/'evidence/card0-58as-a',0,'2026-10-19T00:00:00Z',library_path())
assert list(commands)==['K1a','K1b','KD','W2m','WS','WS128x','WS128'] and Q.GAP_SECONDS==90
manifest=D.oracle_inputs();native={}
for window in ('KD','W2m','WS','WS128x','WS128'):
 args=SimpleNamespace(window=window,view='down-tile16',output=P/'evidence/UNLAUNCHED',miss_mode='zerocopy')
 cmd=D.native_command(args,manifest,P/'evidence/UNLAUNCHED.tsv');C.check(cmd)
 assert cmd[cmd.index('--wait-seconds')+1]=='300'
 assert cmd[cmd.index('--wait-policy')+1]=='spin'
 assert cmd[cmd.index('--max-new')+1]==('8' if window in ('KD','W2m') else '128')
 native[window]=cmd
for f in P.glob('*.py'):ast.parse(f.read_text(),filename=str(f))
job=dict(name='packet58asc-chain-A',lane='A',argv=['/usr/bin/python3','-B',str(P/'queue_runner.py'),'--authorized-device-window','--card','0','--view','down-tile16','--output-root',str(P/'evidence/card0-58as-a'),'--fault-review','{REVIEW}'],review=str(P/'fault_review.py'),planned_write_bytes=sum(Q.W.WRITES['K1' if w.startswith('K1') else w] for w in Q.ORDER),plan=dict(rehearsal_only=True,actual_unit='packet58-onecard-58as-a',scope='whole-host',host_required_available_bytes=98990252032,entry_rehearsal=dict(binaries=[dict(path=str((P/'build/device/own-rt-iq3').relative_to(ROOT)),sha256=sha(P/'build/device/own-rt-iq3')),dict(path=str((P/'build/device/p58-cache-fixtures').relative_to(ROOT)),sha256=sha(P/'build/device/p58-cache-fixtures'),args=['--help'],returncode=0,contains='--output')])))
proposal=O/'entry-proposal.jsonl';proposal.write_text(json.dumps(job)+'\n')
with tempfile.TemporaryDirectory(prefix='packet58asc-plan-') as tmp:
 (Path(tmp)/'queue-A.txt').write_bytes(proposal.read_bytes())
 cp=subprocess.run([sys.executable,'-B',str(ROOT/'experiments/own-xpu-runtime/ops/lane-queue/lanequeue.py'),'plan','--lane','A','--directory',tmp],stdin=subprocess.DEVNULL,capture_output=True,text=True)
(O/'queue-plan.log').write_text(cp.stdout+cp.stderr)
assert cp.returncode==0,cp.stdout+cp.stderr
plans=[json.loads(line) for line in cp.stdout.splitlines()];assert len(plans)==1 and plans[0]['plan']=='passed'
save(O/'chain-checks.json',dict(passed=True,device_executed=False,windows=list(commands),gap_seconds=90,native_commands=native,temporary_queue=True,live_queue_changed=False,native_argv_static_only=True,native_interface_passed=False,queue_plan=plans,bracket_binary_sha256=sha(P/'build/device/own-rt-iq3'),peak_rss_bytes=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024))
print('PASS seven-window argv, exact oracle inputs and temporary lanequeue plan')
