#!/usr/bin/env python3
"""AFTER parent release only: tiny CPU fixture build/run, never device/model IO."""
import argparse,hashlib,json,os,pathlib,subprocess,time
HERE=pathlib.Path(__file__).resolve().parent;RUNTIME=HERE.parents[2];SRC=RUNTIME/'engine/src'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def need(ok,msg):
 if not ok:raise ValueError(msg)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('output',type=pathlib.Path);a=parser.parse_args()
 pins=json.loads((HERE/'source-pins.json').read_text())
 for name,p in pins['files'].items():
  need(sha(SRC/name)==p['base_sha256'],'canonical base drift '+name)
  need(sha(HERE/'overlay/engine/src'/name)==p['candidate_sha256'],'candidate drift '+name)
 need(os.getpriority(os.PRIO_PROCESS,0)==19 and set(os.sched_getaffinity(0))<=set(range(8,16)),'nice19 cores8-15')
 a.output.mkdir(exist_ok=False);binary=a.output/'fixture'
 command=['/usr/bin/g++','-std=c++20','-O2','-g0','-DOWN_RT_HOST_ONLY','-fno-fast-math','-ffp-contract=off','-ffunction-sections','-fdata-sections',
  '-I',str(HERE/'overlay/engine/src'),'-I',str(SRC),'-I',str(HERE),str(HERE/'test_lookup_view.cpp'),
  str(HERE/'overlay/engine/src/stage2/packet2/loader/gguf.cpp'),'-Wl,--gc-sections','-o',str(binary)]
 receipt={'status':'building','device_calls':0,'model_payload_reads':False,'compile_argv':command,
  'sources':{str(f.relative_to(HERE)):sha(f)for f in HERE.rglob('*')if f.is_file() and f.suffix in ('.cpp','.hpp','.inc','.py','.patch')},'native_pins':pins}
 def save():(a.output/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
 save();start=time.monotonic();c=subprocess.run(command,capture_output=True,text=True)
 (a.output/'compile.stdout').write_text(c.stdout);(a.output/'compile.stderr').write_text(c.stderr)
 receipt.update(compile_rc=c.returncode,compile_seconds=time.monotonic()-start)
 if c.returncode:receipt['status']='compile-failed';save();raise SystemExit(c.returncode)
 receipt['binary_sha256']=sha(binary);run=subprocess.run([str(binary),str(a.output/'synthetic')],capture_output=True,text=True)
 (a.output/'run.stdout').write_text(run.stdout);(a.output/'run.stderr').write_text(run.stderr)
 receipt.update(run_rc=run.returncode,status='passed'if run.returncode==0 else'fixture-failed');save()
 print(json.dumps({'status':receipt['status'],'receipt':str(a.output/'receipt.json')}));raise SystemExit(run.returncode)
if __name__=='__main__':main()
