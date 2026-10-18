"""Manual chain entry. Choice and lane-B pause are checked at launch time."""
import os,subprocess,sys
from pathlib import Path
from chain_adapter import install,O,P,ROOT
sys.path.insert(0,str(ROOT/'experiments/own-xpu-runtime/ops'))
from launch_env import library_path

def embed_environment(argv):
 for i,v in enumerate(argv):
  if v.startswith('LD_LIBRARY_PATH='):argv[i]='LD_LIBRARY_PATH='+library_path();return argv
 raise ValueError('missing closed library environment')
def main():
 assert set(os.environ)<={'PATH','OMP_NUM_THREADS','LD_LIBRARY_PATH','LC_CTYPE'}
 assert os.environ.get('PATH')=='/usr/bin:/bin' and os.environ.get('OMP_NUM_THREADS')=='2' and os.environ.get('LD_LIBRARY_PATH')==library_path()
 from source_gate136 import oracle
 oracle();install()
 if len(sys.argv)>1 and sys.argv[1]=='queue' and '--plan' not in sys.argv:
  from verify_ready import verify
  result=verify()
  from compositions import selected
  assert selected()==result['selection'],'chain differs from evidence-selected smoke'
  # Existing per-window Reservation/DrainPermit owns any pause. Do not persist
  # a preparation-time PAUSE-B decision or modify the live queue pause marker.
 import chain103
 q,w=chain103.install();original=q.commands
 def commands(out):
  rows=original(out)
  for argv in rows.values():
   i=argv.index(str(P/'chain103.py'));argv[i]=str(O/'chain_entry.py');embed_environment(argv)
  return rows
 commands._packet103e=True;q.commands=commands
 def input_preflight(args,window=None):
  argv=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(O/'chain_adapter.py'),'check_inputs.py','--output-root',str(args.output_root)]
  if args.prefix_windows:argv+=['--prefix-windows',*map(str,args.prefix_windows)]
  if window:argv+=['--window',window]
  subprocess.run(argv,stdin=subprocess.DEVNULL,check=True)
 q.input_preflight=input_preflight
 return chain103.main()
if __name__=='__main__':raise SystemExit(main())
