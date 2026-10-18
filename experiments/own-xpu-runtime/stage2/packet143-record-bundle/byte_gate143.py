"""Every composition through real CPU miniature target+draft+rollback paths.
No model payloads, full-shape metadata or device backends. Exact token, layer,
draft-proposal and final-state bytes are compared across fresh processes.
"""
import argparse,gzip,hashlib,json,os,resource,shutil,subprocess,sys,tempfile
from pathlib import Path
from unittest.mock import patch
from compositions import P,ROOT,all_compositions,key,native,save,read,sha
sys.path.insert(0,str(P/'v5'))
from build_engine import compiler_turn,limits
sys.path.remove(str(P/'v5'))
import pipeline
B=P/'v5/build'
def intel_host():
 prior=read(P/'v5/evidence/build.json')['commands'];out=B/'intel-host';out.mkdir(exist_ok=True)
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args[0]='/opt/intel/oneapi/compiler/2026.0/bin/icpx';args[args.index('-o')+1]=str(out/'entry-main.o');args=[a for a in args if a!='-fopenmp']+['-qopenmp']
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link[0]='/opt/intel/oneapi/compiler/2026.0/bin/icpx';link=[str(out/'entry-main.o') if a.endswith('/entry-main.o') else a for a in link];link[link.index('-o')+1]=str(out/'own-rt-iq3');link=[a for a in link if a!='-fopenmp']+['-qopenmp']
 for label,cmd in [('compile',args),('link',link)]:
  with compiler_turn(),(out/(label+'.log')).open('w') as f:subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=600)
 # Keep binary, exact command and object digest; this new disposable object is reconstructible.
 save(P/'evidence/intel-host-build.json',dict(passed=True,device_executed=False,commands=[args,link],object_sha256=sha(out/'entry-main.o'),binary_sha256=sha(out/'own-rt-iq3')))
 (out/'entry-main.o').unlink();limits()
def run_one(selection,binary,repeat):
 with tempfile.TemporaryDirectory(prefix='p143-mini-') as tmp:
  tmp=Path(tmp);adapter=tmp/'adapter';adapter.mkdir();dest=tmp/'run';s=native(selection)
  # Same explicit miniature projection as packet137; actual production shape
  # has a separate admission gate. New dimensions remain exactly selected.
  s['choices'].update(experts='wide64',head='production');save(adapter/'selection.json',s)
  args=pipeline.parser().parse_args(['--binary',str(binary),'--output',str(dest),'--mini','--context','256','--tokens','24','--seconds','180','--wait-seconds','120','--native-nice','19','--draft','mtp','--draft-rank','1','--target-split','0','--controller','native','--timing','token','--retain-steps','1-24'])
  args.host_memory='resident';args.selection_sha256=sha(adapter/'selection.json')
  try:
   with patch.object(pipeline,'P',adapter):result=pipeline.run(args,environment=__import__('launch_env143').environment())
  except Exception:
   failure=P/'evidence'/('mini-failed-'+key(selection))
   if not failure.exists():shutil.copytree(dest,failure)
   raise
  if not result['passed']:
   logs={str(f.relative_to(dest)):f.read_text()[-8000:] for f in dest.glob('rank*/*.log')};save(P/'evidence/mini-failure.json',dict(result=result,logs=logs));raise ValueError(result.get('error',logs))
  fixtures={str(f.relative_to(dest)):sha(f) for rank in ('rank0','rank1') for f in (dest/rank).glob('step*/layer-*.bf16')}
  assert len(fixtures)==96 and len(result['tokens'])==24
  proposals=[{k:r[k] for k in ('draft_position','confirmed_token','guess','head')} for line in (dest/'rank1/draft-rows.jsonl').read_text().splitlines() if 'guess' in (r:=json.loads(line))]
  state=dest/'rank1/draft-final-state';states={str(f.relative_to(state)):sha(f) for f in state.rglob('*') if f.is_file() and f.suffix in ('.bin','.bf16','.f32','.u32')}
  identity=dict(tokens=result['tokens'],fixtures=fixtures,proposals=proposals,draft_state=states)
  # Identical table-vs-original dumps are required, including observability materialization.
  raw=(json.dumps(identity,sort_keys=True)+'\n').encode();digest=hashlib.sha256(raw).hexdigest()
  return identity,dict(compiler='Intel' if 'intel-host' in str(binary) else 'GNU',repeat=repeat,selection=selection,output_sha256=digest,fixture_count=len(fixtures),proposals=len(proposals),stats=result['stats'])
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--build-intel',action='store_true');ap.add_argument('--single',action='store_true');ap.add_argument('--filter');a=ap.parse_args();limits()
 if a.build_intel:intel_host()
 expected=None;rows=[]
 for compiler,folder in [('GNU','gnu-host'),('Intel','intel-host')]:
  binary=B/folder/'own-rt-iq3';links=subprocess.check_output(['readelf','-d',str(binary)],text=True).lower();assert not any(x in links for x in ('libsycl','libze_loader','libur_loader','libopencl'))
  for selection in all_compositions():
   if a.filter and key(selection)!=a.filter:continue
   for repeat in (1,2):
    identity,row=run_one(selection,binary,repeat)
    if expected is None:expected=identity
    assert identity==expected,'composed output differs: '+key(selection)+' '+compiler
    rows.append(row);print(compiler,key(selection),repeat,'MATCH',flush=True)
    if a.single:return
 raw=(json.dumps(expected,sort_keys=True)+'\n').encode();archive=P/'evidence/mini-byte-reference.json.gz';archive.write_bytes(gzip.compress(raw,mtime=0))
 save(P/'evidence/bytes143.json',dict(passed=True,device_executed=False,model_payload_read=False,full_shape_read=False,rows=rows,compositions=16,fresh_processes=128,expected_sha256=hashlib.sha256(raw).hexdigest(),fixture=str(archive.relative_to(ROOT)),fixture_sha256=sha(archive),sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'byte_gate143.py',P/'pipeline.py',P/'compositions.py',P/'class_layout.hpp',P/'token_input.hpp')},binaries={str((B/m/'own-rt-iq3').relative_to(ROOT)):sha(B/m/'own-rt-iq3') for m in ('gnu-host','intel-host')},max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,scope='real miniature composed runtime; packet100/split-head miniature projection only; production shape and device quality separate'))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
