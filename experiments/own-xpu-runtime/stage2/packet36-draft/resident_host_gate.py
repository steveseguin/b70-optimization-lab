"""Small host model verifies resident prepared-binding swaps, including ASan."""
import json,os,shutil,time
from pipeline import P,parser,run,save,sha
from gates import fixture_hashes,states
from cpu_gates import host
rows=[]
for compiler in ('gnu-host','icpx-host','asan'):
 binary=P/'build'/compiler/'own-rt-iq3';host(binary)
 if compiler=='asan':os.environ['ASAN_OPTIONS']='detect_leaks=1:abort_on_error=1';os.environ['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
 root=P/'build'/f'resident-host-{compiler}-{time.time_ns()}';root.mkdir()
 prior=json.loads((P/('mini-'+compiler+'.json')).read_text());expected=prior['reference_tokens'];want=prior['fixture_sha256'];control=None
 for mode in ('none','ngram','hit','miss','mtp'):
  out=root/mode;script=root/(mode+'.txt')
  a=parser().parse_args(['--binary',str(binary),'--output',str(out),'--mini','--dump-state','--draft','script' if mode in ('hit','miss') else mode])
  a.host_memory='resident';a.dispatch=P/'dispatch-all-new.json'
  if mode in ('hit','miss'):
   script.write_text(' '.join(map(str,expected[:7] if mode=='hit' else [(x+1)%16 for x in expected[:7]])));a.script=script
  result=run(a)
  assert result['tokens']==expected and fixture_hashes(out)==want
  current=states(out)
  if control is None:control=current
  assert current==control
  rows.append(dict(compiler=compiler,mode=mode,binary_sha256=sha(binary),tokens=8,fixtures=32,state_files=len(current),stats=result['stats']))
 shutil.rmtree(root)
save(P/'resident-host-gates.json',dict(passed=True,device_executed=False,cases=len(rows),rows=rows))
print(len(rows),'resident binding-bank gates PASS')
