"""Bounded operator bytes on GNU/Intel; no CPU model execution."""
from pathlib import Path
import json,subprocess,os,resource
from build_engine import P,ROOT,BASE,limits,sha,save

def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 prior=json.loads((BASE/'engine-commands.json').read_text())
 commands=[];runs=[]
 for mode in ('gnu-host','device'):
  cc=next(r['command'] for r in prior if r['name']==mode+'-entry-main')
  compiler=cc[0];label='gnu' if mode=='gnu-host' else 'intel'
  # No -fsycl: Intel is used only as a host compiler here.
  flags=['-std=c++20','-O1','-ffp-contract=off','-fno-fast-math','-DOWN_RT_HOST_ONLY','-I'+str(P),'-I'+str(P.parents[2]/'stage1/packet3-prep/src')]
  for stem in ('p69_fixture','p59_fixture'):
   binary=P/'build'/f'{stem}-{label}'
   cmd=[compiler,*flags,str(P/(stem+'.cpp')),'-o',str(binary)];commands.append(cmd)
   with (P/'evidence'/f'{stem}-{label}-compile.log').open('w') as log:subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
   outputs=[]
   for repeat in (1,2):
    out=P/'evidence'/f'{stem}-{label}-{repeat}.bin'
    args=[str(binary),str(out)]
    if stem=='p69_fixture':args.append(str(out.with_suffix('.actual.bin')))
    subprocess.run(args,check=True,stdin=subprocess.DEVNULL,timeout=120)
    if stem=='p69_fixture':assert sha(out)==sha(out.with_suffix('.actual.bin'))
    outputs.append(sha(out));runs.append(dict(compiler=label,fixture=stem,repeat=repeat,sha256=sha(out),bytes=out.stat().st_size))
   assert len(set(outputs))==1
 for stem in ('p69_fixture','p59_fixture'):assert len({r['sha256'] for r in runs if r['fixture']==stem})==1
 sources={str(f.relative_to(ROOT)):sha(f) for f in P.glob('*.hpp')}
 sources.update({str((P/n).relative_to(ROOT)):sha(P/n) for n in ('p69_fixture.cpp','p59_fixture.cpp','cpu_gate.py','p69_head.cpp','main.cpp','mtp.hpp','p49d_submit.cpp')})
 save(P/'evidence/cpu-gates.json',dict(passed=True,device_executed=False,cpu_model_executed=False,
  target_gate='512 production-K cases: all 32 FP32 lane sums, final FP32 sum, BF16 bytes exact vs p33; padded WG64/WG128 coverage',
  draft_gate='two fresh CPU processes per compiler: split32 contexts 2,31,33,65 at M1/M2 plus inherited p59 HC/norm/linear fixtures',
  argmax='unchanged target source and full logits; original tie rule retained',runs=runs,commands=commands,sources=sources,peak_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss))
 print('PASS operator bytes and draft repeats; no CPU model execution')
if __name__=='__main__':main()
