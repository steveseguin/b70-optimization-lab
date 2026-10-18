"""Initial source copy only. Preserve every packet124c symlink, including oracle.

The committed packet136 sources contain the separately reviewed packet131b
changes and orchestration. This helper reproduces the initial copy operation,
not those later edits or the CPU receipts. Never run over an existing packet.
"""
import json,os,shutil,subprocess
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');BASE=ROOT/'experiments/own-xpu-runtime'
O=BASE/'ops/packet136-orchestration';P=BASE/'stage2/packet136-record-bundle';OLD=P.with_name('packet124c-record-bundle')
def links(p):
 out=subprocess.check_output(['find',str(p),'-type','l','-printf','%P\t%l\n'],stdin=subprocess.DEVNULL,text=True)
 return dict(line.split('\t',1) for line in out.splitlines())
def main():
 assert not P.exists() and shutil.disk_usage('/').free>=25_000_000_000
 before=links(OLD)
 def ignore(path,names):
  rel=Path(path).relative_to(OLD)
  return [n for n in names if n=='__pycache__' or (rel==Path('.') and n in ('build','selections','submission'))]
 shutil.copytree(OLD,P,symlinks=True,ignore=ignore)
 for name,target in before.items():
  dest=P/name;dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.is_symlink():dest.symlink_to(target)
 assert links(P)==before
 print('All',len(before),'parent symlinks preserved')
if __name__=='__main__':
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 main()
