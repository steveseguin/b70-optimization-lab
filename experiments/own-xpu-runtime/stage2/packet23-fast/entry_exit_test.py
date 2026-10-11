"""Compile native entry shims with CPU stubs; never run a device executable."""
import subprocess,json,hashlib
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';D=B/'entry-exit-r3'
def main():
 D.mkdir(exist_ok=True);rows=[]
 for name,entry in [('own-rt-iq3','packet23_model_entry'),('fused-fixtures','packet23_gemv_fixture_entry'),('nongemv-fixtures','packet23_nongemv_fixture_entry')]:
  source=B/(name+'-entry.cpp');stub=D/(name+'.cpp');binary=D/name
  stub.write_text('int '+entry+'(int,char**){return 37;}\n')
  subprocess.run(['g++',str(source),str(stub),'-o',str(binary)],check=True)
  r=subprocess.run([str(binary)],check=False);assert r.returncode==37
  rows.append(dict(entry=name,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),expected=37,actual=r.returncode))
 (P/'entry-exit-tests.json').write_text(json.dumps(dict(passed=True,device_executed=False,cases=rows),indent=2)+'\n')
 print('3/3 CPU entry-shim exit codes preserved')
if __name__=='__main__':main()
