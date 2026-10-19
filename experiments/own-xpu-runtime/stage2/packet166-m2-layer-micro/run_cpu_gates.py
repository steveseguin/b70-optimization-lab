"""GNU/Intel byte gate; real model reads require an empty timing window."""
import argparse,hashlib,json,os,resource,subprocess,sys,time
from pathlib import Path
from build_engine import limits,P,ROOT,sha
import compile_turn
import launch_env

def native_rows(path):
 rows=[json.loads(s) for s in path.read_text().splitlines()]
 assert rows[-1]['passed'] and rows[-1]['zero_errors'] and rows[-1]['finite_outputs'] and rows[-1]['backend']=='cpu'
 data={(r['layer'],r['position'],r['buffer']):(r['compared_bytes'],r['sha256']) for r in rows if r['kind']=='bytes'}
 assert all(r['different_bytes']==0 for r in rows if r['kind']=='bytes')
 assert {(l,p) for l,p,_ in data}=={(l,p) for l in (0,3) for p in (2,3,31)}
 return data

def blockers():
 found=[dict(coordination=name) for pid,name in compile_turn.active() if pid<0]
 for p in Path('/proc').iterdir():
  if not p.name.isdigit():continue
  try:
   comm=(p/'comm').read_text().strip()
   if comm in ('own-rt-iq3','micro-device'):found.append(dict(pid=int(p.name),comm=comm))
  except OSError:pass
 return found

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--real',action='store_true');args=ap.parse_args();limits()
 build=json.loads((P/'evidence/build.json').read_text());assert all(sha(ROOT/f)==h for r in build['records'] for f,h in r['sources'].items()),'native source pins stale: rebuild before CPU qualification'
 mode='real' if args.real else 'synthetic';out=P/'evidence'/('cpu-'+mode+'-'+str(time.time_ns()));out.mkdir()
 if args.real and blockers():
  row=dict(passed=False,blocked=True,reason='active timing process: no GGUF/full-shape reads permitted',processes=blockers(),device_executed=False,real_weights=True)
  (out/'blocked.json').write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row));return 2
 records=[];traces=[]
 for compiler in ('gnu-host','intel-host'):
  binary=P/'build'/('micro-'+compiler);help_=subprocess.run([str(binary),'--help'],env=launch_env.environment(),stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
  argv=['/usr/bin/ionice','-c3',str(binary),'--rank','0','--mode','cpu','--weights',mode,'--repeats','200']
  assert all(v in help_.stdout for v in argv[3:] if v.startswith('--'))
  stdout=out/(compiler+'.jsonl');stderr=out/(compiler+'.stderr')
  with stdout.open('x') as so,stderr.open('x') as se:
   result=subprocess.run(argv,env=launch_env.environment(),stdin=subprocess.DEVNULL,stdout=so,stderr=se)
  records.append(dict(compiler=compiler,argv=argv,returncode=result.returncode,binary_sha256=sha(binary),stdout=str(stdout.relative_to(ROOT)),stdout_sha256=sha(stdout)))
  if result.returncode:
   (out/'failure.json').write_text(json.dumps(dict(passed=False,records=records),indent=2)+'\n');raise RuntimeError('native CPU gate failed; see '+str(stderr))
  traces.append(native_rows(stdout))
 assert traces[0]==traces[1],'GNU/Intel bytes differ'
 row=dict(passed=True,real_weights=args.real,device_executed=False,compiler_exactness=True,compared_buffers=len(traces[0]),records=records,peak_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024)
 assert row['peak_rss_bytes']<=4*1024**3
 if args.real:
  oracle=P/'evidence/real-oracle.tsv';oracle.write_text(''.join(f'{l} {pos} {name} {v[1]}\n' for (l,pos,name),v in sorted(traces[0].items())))
  row['oracle_sha256']=sha(oracle)
 (out/'result.json').write_text(json.dumps(row,indent=2)+'\n')
 (P/'evidence'/('cpu-'+mode+'-parity.json')).write_text(json.dumps(row,indent=2)+'\n');print(json.dumps(row,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
