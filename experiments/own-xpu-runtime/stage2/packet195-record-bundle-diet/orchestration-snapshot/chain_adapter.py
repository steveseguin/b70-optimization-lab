"""Packet155 chain adapter: local native closure and unchanged shared oracle."""
import hashlib,json,runpy,sys
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet195-record-bundle-diet'
sys.path.insert(0,str(P))
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def install():
 from reuse_build import verify_native
 verify_native()
 import shared_oracle
 assert (P/'oracle').is_symlink() and (P/'oracle').resolve()==shared_oracle.AUTHORITY.resolve()
 shared_oracle.P=P;shared_oracle.static_binding()
 assert sha(P/'drain_gate.py')==sha(O/'drain_gate.py'),'drain copies differ'
 return shared_oracle
if __name__=='__main__':
 script=sys.argv.pop(1);assert script in ('fast_reseal.py','check_inputs.py','chain103.py')
 install();sys.argv[0]=str(P/script);runpy.run_path(str(P/script),run_name='__main__')
