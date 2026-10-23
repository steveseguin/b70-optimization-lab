#!/usr/bin/env python3
"""CPU-only reproducible packet30 gate adaptation; no device API or discovery."""
import argparse,hashlib,json,os,subprocess
from pathlib import Path
P=Path(__file__).resolve().parent
FLAGS=['-O2','-std=c++20','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 a=argparse.ArgumentParser();a.add_argument('--seal-existing',action='store_true');args=a.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 commands=[];binaries={};receipts={}
 for name in ('attention','small'):
  source=P/f'p30_{name}_cpu.cpp';binary=P/'build'/f'p30-{name}-cpu';receipt=P/f'p30-{name}-cpu.json'
  argv=['nice','-n','19','ionice','-c','3','/usr/bin/g++',*FLAGS,'-I',str(P),'-I',str(P.parents[1]/'stage1/packet3-prep/src'),'-I',str(P.parent/'packet2/kernels'),'-I',str(P.parent/'packet2/loader'),str(source),'-o',str(binary)]
  commands.append(dict(kind='compile-and-link',argv=argv))
  if not args.seal_existing:
   subprocess.run(argv,check=True)
   with receipt.open('w') as output:subprocess.run(['nice','-n','19','ionice','-c','3',str(binary)],stdout=output,check=True)
  result=json.loads(receipt.read_text());assert result['passed'];receipts[receipt.name]={'sha256':sha(receipt),'result':result};binaries[str(binary.relative_to(P))]=sha(binary)
 sources={f.name:sha(f) for f in sorted(P.glob('p30*')) if f.suffix in ('.hpp','.cpp')}
 out=dict(schema='packet38.p30-cpu-gates.v1',passed=True,device_executed=False,arithmetic='iq3-p17-detmath-v2',precision_flags_compile_and_link=FLAGS,commands=commands,binaries_sha256=binaries,sources_sha256=sources,receipts=receipts)
 (P/'p38-kernel-gates.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
