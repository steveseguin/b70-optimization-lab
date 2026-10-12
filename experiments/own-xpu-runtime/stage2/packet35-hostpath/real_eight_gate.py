"""CPU-only eight-token v2 oracle check; streaming, two threads, <=8 GiB AS."""
import hashlib,json,os,resource,subprocess,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ['OMP_NUM_THREADS']=='2'
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 binary=B/'host/own-rt-iq3';before=sha(binary)
 elf=subprocess.check_output(['readelf','-d',str(binary)],text=True)
 assert not any(s in elf.lower() for s in ('libsycl','libze_loader','libur_loader','libopencl'))
 out=B/('real-eight-'+str(time.time_ns()));oracle=P.parents[2]/'qwen38-flash-next-ud-iq3xxs-b70/packet3-runtime-oracle/runs/arithmetic-v2-detmath-20261011/incident-retrospective'
 cmd=[str(binary),'--audit-prepare-each','--cards','1','--card','0','--memory','layer-streaming','--dispatch',str(P/'dispatch-all-new.json'),'--gemv','r5','--timing','token','--stage','decode','--context','256','--input',str(B/'input/tokens.txt'),'--max-new','8','--plan',str(B/'input/plan.tsv'),'--identity',str(B/'input/identity.tsv'),'--model-dir',json.loads((B/'input/input.json').read_text())['model_dir'],'--oracle',str(oracle),'--output',str(out)]
 start=time.monotonic()
 with out.with_suffix('.log').open('w') as log:result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
 r=json.loads((out/'receipt.json').read_text());expected=json.loads((oracle/'result.json').read_text())['tokens'][:8]
 assert result.returncode==0 and r['passed'] and r['oracle_exact'] and r['tokens']==expected and sha(binary)==before
 rows=[dict(path=str(f.relative_to(out)),sha256=sha(f),oracle_sha256=sha(oracle/f.relative_to(out))) for f in out.glob('step*/layer-*.bf16')]
 assert len(rows)==384 and all(x['sha256']==x['oracle_sha256'] for x in rows)
 audit=[json.loads(line) for line in (out/'argument-equivalence.jsonl').open()];assert audit and all(x['legacy_argument_hex']==x['prepared_argument_hex'] for x in audit)
 receipt=dict(prepared_argument_comparisons=len(audit),argument_log_sha256=sha(out/'argument-equivalence.jsonl'),prepared_mode='one-card per-operation preparation after layer staging; production streaming remains legacy',dispatch="all-new",passed=True,device_executed=False,argv=cmd,binary_sha256=before,tokens=r['tokens'],layer_matches=384,layers=rows,seconds=time.monotonic()-start,maxrss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss)
 (P/'real-eight.json').write_text(json.dumps(receipt,indent=2)+'\n');print('8/8 tokens and 384/384 layers exact')
if __name__=='__main__':main()
