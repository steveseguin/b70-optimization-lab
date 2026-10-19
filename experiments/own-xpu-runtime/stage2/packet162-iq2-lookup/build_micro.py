"""CPU builds only, under the shared compiler turn."""
import json, subprocess, shlex, hashlib, resource, sys, shutil
from pathlib import Path
from analyze import limits
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
sys.path.insert(0,str(P.parents[1]/'ops'))
from compile_turn import turn

def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
 limits();assert shutil.disk_usage('/').free >= 27_000_000_000, 'CPU preparation floor';(P/'evidence/micro-prep').mkdir(exist_ok=True)
 flags=['/opt/intel/oneapi/compiler/2026.0/bin/icpx', '-std=gnu++20', '-O2', '-Werror=return-type', '-fno-fast-math', '-ffp-contract=off', '-fdenormal-fp-math=ieee', '-foffload-fp32-prec-div', '-foffload-fp32-prec-sqrt', '-fsycl', '-Werror=deprecated-this-capture', '-I/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks/build-snapshot/checked/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks', '-I/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet131-snapshot-banks', '-I/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet136-record-bundle', '-I/home/steve/llm-optimizations/experiments/own-xpu-runtime/stage2/packet162-iq2-lookup/native-pinned/experiments/own-xpu-runtime/stage2/packet28-dense']
 records=[]
 for name,cmd in [('micro-host',['/usr/bin/g++','-std=c++20','-O2','-fno-fast-math','-ffp-contract=off','-DOWN_RT_HOST_ONLY',*filter(lambda s:s.startswith('-I'),flags)]),('micro-device',flags)]:
  out=P/'build'/name;cmd=cmd+['-MMD','-MF',str(out)+'.d',str(P/'micro.cpp'),'-o',str(out)]
  with turn(),(P/'evidence/micro-prep'/f'{name}-build.log').open('w') as f:
   subprocess.run(cmd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,check=True)
  deps=shlex.split(Path(str(out)+'.d').read_text().replace('\\\n',' ').split(':',1)[1])
  records.append(dict(command=cmd,binary=str(out.relative_to(ROOT)),sha256=sha(out),sources={str(Path(p).resolve().relative_to(ROOT)):sha(p) for p in deps if Path(p).is_file() and Path(p).resolve().is_relative_to(ROOT)}))
 (P/'evidence/micro-prep/build.json').write_text(json.dumps(dict(passed=True,device_executed=False,records=records,max_rss_kib=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss),indent=2)+'\n')
if __name__=='__main__':main()
