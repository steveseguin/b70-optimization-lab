"""Build/run only a host chain overlay; never loads accelerator libraries."""
import argparse,gzip,hashlib,json,os,resource,shlex,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;OLD=P.parent/'packet29-merged';B=P/'build'/'host-gate'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--build-only',action='store_true');ap.add_argument('--mini',action='store_true');a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 B.mkdir(parents=True,exist_ok=True)
 if a.build_only:
  source=(OLD/'main.cpp').read_text();source='#include "fused.hpp"\n'+source
  marker='  flash::Event enqueue(const flash::Launch &l, flash::Event dep) override {'
  assert source.count(marker)==1;source=source.replace(marker,(P/'host_overlay.inc').read_text()+'\n'+marker)
  marker='    if (l.op == "lookup") { fp32_sources[c]=0;'
  assert source.count(marker)==1;source=source.replace(marker,'    if (p39_skip(l)) {}\n    else if (l.op == "lookup") { fp32_sources[c]=0;')
  marker='      linear(l);\n    } else {'
  assert source.count(marker)==1;source=source.replace(marker,'      linear(l);p39_after(l);\n    } else {')
  marker='      // One token-boundary readback contains sticky error and greedy output.'
  assert source.count(marker)==1;source=source.replace(marker,'      std::cerr << "packet39 host fused rows=" << e->p39_rows << " skipped sites=" << e->p39_removed << "\\n";\n'+marker)
  (B/'main.cpp').write_text(source)
  (B/'rope.bf16').write_bytes((OLD/'rope.bf16').read_bytes())
  flags=['-std=gnu++20','-O3','-march=native','-fopenmp','-fno-fast-math','-ffp-contract=off','-Werror=return-type','-DOWN_RT_HOST_ONLY']
  inc=[P,OLD,OLD/'build/host/validation',OLD/'../../stage1/packet3-prep/src',OLD/'../packet2/kernels',OLD/'../packet2/loader']
  compile=['g++',*flags,*['-I'+str(x) for x in inc],'-c',str(B/'main.cpp'),'-o',str(B/'main.o')]
  with (B/'compile.log').open('w') as f:subprocess.run(compile,stdout=f,stderr=subprocess.STDOUT,check=True)
  objects=sorted(x for x in (OLD/'build/host/CMakeFiles/programs.dir').rglob('*.o') if not x.name.startswith('entry-'))
  link=['g++','-fno-fast-math','-ffp-contract=off','-fopenmp',str(B/'main.o'),*[str(x) for x in objects],'-lcrypto','-o',str(B/'own-rt-iq3-host')]
  with (B/'link.log').open('w') as f:subprocess.run(link,stdout=f,stderr=subprocess.STDOUT,check=True)
  d=json.loads((OLD/'dispatch-all-new.json').read_text());d['fusions']['attn.combine+norm']='packet18';d['fusions']['ffn.combine+norm']='packet18'
  (B/'dispatch.json').write_text(json.dumps(d,indent=2)+'\n')
  receipt=dict(device_executed=False,compile=compile,link=link,binary_sha256=sha(B/'own-rt-iq3-host'),source_sha256=sha(B/'main.cpp'),overlay_sha256=sha(P/'host_overlay.inc'),fused_sha256=sha(P/'fused.hpp'),objects=[dict(path=str(x.relative_to(OLD)),sha256=sha(x)) for x in objects])
  (P/'host-build-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');return
 binary=B/'own-rt-iq3-host';before=sha(binary)
 elf=subprocess.check_output(['readelf','-d',str(binary)],text=True)
 assert not any(s in elf.lower() for s in ('libsycl','libze_loader','libur_loader','libopencl'))
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 out=B/(('mini-' if a.mini else 'real-eight-')+str(time.time_ns()))
 cmd=[str(binary),'--cards','1','--card','0','--memory','layer-streaming','--dispatch',str(B/'dispatch.json'),'--gemv','r5','--timing','token','--stage','decode','--context','256','--max-new','8','--output',str(out)]
 oracle=P.parents[2]/'qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective'
 if a.mini:cmd+=['--mini','--max-new','4']
 else:
  inputs=OLD/'build/input';cmd+=['--input',str(inputs/'tokens.txt'),'--plan',str(inputs/'plan.tsv'),'--identity',str(inputs/'identity.tsv'),'--model-dir',json.loads((inputs/'input.json').read_text())['model_dir'],'--oracle',str(oracle)]
 start=time.monotonic()
 with out.with_suffix('.log').open('w') as f:result=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 r=json.loads((out/'receipt.json').read_text()) if (out/'receipt.json').exists() else {}
 rows=[]
 if not a.mini:
  rows=[dict(path=str(f.relative_to(out)),sha256=sha(f),oracle_sha256=sha(oracle/f.relative_to(out))) for f in sorted(out.glob('step*/layer-*.bf16'))]
 expected=json.loads((oracle/'result.json').read_text())['tokens'][:8] if not a.mini else r.get('tokens')
 passed=result.returncode==0 and r.get('passed') and r.get('tokens')==expected and sha(binary)==before and (a.mini or r.get('oracle_exact') and len(rows)==384 and all(x['sha256']==x['oracle_sha256'] for x in rows))
 raw=(out/'receipt.json').read_bytes() if (out/'receipt.json').exists() else b'{}';(P/'evidence').mkdir(exist_ok=True);archive=P/'evidence'/('host-mini-runtime.json.gz' if a.mini else 'host-real-eight-runtime.json.gz');archive.write_bytes(gzip.compress(raw,mtime=0))
 receipt=dict(passed=bool(passed),device_executed=False,actual_chain_overlay=True,smoke_only=a.mini,fusion_kinds=['expert_act','down_status','silu_div4','shared_act','attention_combine','shared_combine','gdn_conv'],argv=cmd,returncode=result.returncode,binary_sha256=before,seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,tokens=r.get('tokens'),layer_matches=sum(x['sha256']==x['oracle_sha256'] for x in rows),layers=rows,source_receipt_sha256=hashlib.sha256(raw).hexdigest(),source_receipt_archive=str(archive.relative_to(P)),source_summary={k:r[k] for k in ('passed','oracle_exact','tokens','device_executed') if k in r})
 (P/('host-mini.json' if a.mini else 'real-eight.json')).write_text(json.dumps(receipt,indent=2)+'\n')
 print('passed',passed,'layers',len(rows));return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
