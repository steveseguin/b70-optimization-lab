"""Coordinator-only chain entry; every child retains the oracle adapter and limit guard."""
import sys,subprocess
from chain_adapter import install,O,P

def embed_environment(argv):
 from confirm136 import LIBRARIES
 for index,value in enumerate(argv):
  if value.startswith('LD_LIBRARY_PATH='):
   argv[index]='LD_LIBRARY_PATH='+LIBRARIES
   return argv
 raise ValueError('chain child is missing its closed library environment')

def main():
 if "--plan" not in sys.argv:
  from launch_identity import verify as identity
  identity()
 from source_gate136 import oracle
 oracle()
 if '--plan' in sys.argv:
  from verify_cpu import verify
  verify()
 if len(sys.argv)>1 and sys.argv[1]=='queue' and '--plan' not in sys.argv:
  from verify_ready import verify
  verify()
 from exec_limits import install as guard
 guard();install()
 import chain103
 q,w=chain103.install();original=q.commands
 def commands(out):
  rows=original(out)
  for argv in rows.values():
   i=argv.index(str(P/'chain103.py'));argv[i]=str(O/'chain_entry.py')
   embed_environment(argv)
  return rows
 commands._packet103e=True
 q.commands=commands
 def input_preflight(args,window=None):
  argv=['nice','-n','19','taskset','-c','8-15,24-31','python3','-B',str(O/'chain_adapter.py'),'check_inputs.py','--output-root',str(args.output_root)]
  if args.prefix_windows:argv+=['--prefix-windows',*map(str,args.prefix_windows)]
  if getattr(args,'resume_from',None):argv+=['--resume-from',str(args.resume_from)]
  if window:argv+=['--window',window]
  subprocess.run(argv,stdin=subprocess.DEVNULL,check=True)
 q.input_preflight=input_preflight
 return chain103.main()
if __name__=='__main__':raise SystemExit(main())
