"""Actual tiny engine replay/restore and analyzer negatives; no model payload."""
import json,resource,subprocess,sys
from p157_v5_build_engine import P,LOCAL,ROOT,B,CHECKED,sha,save,limits,run

def main():
 limits();prior=json.loads((P/'engine-commands.json').read_text());out=B/'split-cpu';out.mkdir(exist_ok=True)
 args=list(next(r['command'] for r in prior if r['name']=='gnu-host-entry-main'));args=args[:args.index('-o')];i=args.index('-c');del args[i:i+2]
 compile_cmd=[*args,'-c',str(P/'native/split_bytes.cpp'),'-o',str(out/'entry.o')]
 run(compile_cmd,'split-cpu-compile')
 link=list(next(r['command'] for r in prior if r['name']=='gnu-host-link'));link=[str(out/'entry.o') if x.endswith('/entry-main.o') else x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')];link[link.index('-o')+1]=str(out/'fixture')
 run(link,'split-cpu-link');rows=[]
 for mode in ('off','split'):
  row=json.loads((P/'lineage'/mode/'selection.json').read_text());row['choices'].update(head='production',experts='production')
  selection=out/(mode+'.json');save(selection,row)
  for repeat in (1,2):
   dest=out/(mode+str(repeat));cmd=[str(out/'fixture'),str(selection),sha(selection),str(dest),mode]
   cp=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True)
   log=P/'evidence'/('split-bytes-'+mode+str(repeat)+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text()[-6000:]
   rows.append(dict(mode=mode,repeat=repeat,result=json.loads(cp.stdout),log_sha256=sha(log)))
 tests=[]
 for name in ('test_analyze.py','test_timing_report.py'):
  cp=subprocess.run([sys.executable,'-B',str(P/name)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
  log=P/'evidence'/('split-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0,log.read_text();tests.append(name)
 from bracket import compatible,load_config
 off=json.loads((P/'lineage/off/selection.json').read_text());on=json.loads((P/'lineage/split/selection.json').read_text())
 assert compatible([off,on,off,on,off]) and len(load_config(P/'configs/split-bracket.json')['views'])==5
 on['choices']['probe']='xchg'
 try:compatible([off,on])
 except ValueError:pass
 else:raise AssertionError('unregistered exchange mode admitted')
 sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'split_cpu.py',P/'native/split_bytes.cpp',P/'native/split_timing.hpp',P/'analyze.py',P/'test_analyze.py',P/'test_timing_report.py',P/'bracket.py']}
 save(P/'evidence/split-cpu.json',dict(passed=True,device_executed=False,model_payload_read=False,full_shape_read=False,runs=rows,tests=tests,sources=sources,suffix_device_equality_pending=True,peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('Actual miniature token replay and snapshot poison/restore PASS')
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
