"""Document/replay the initial packet137 source copy only, never overwrite a tree.

Final packet139 adds packet136 chain wrappers and the reviewed local diff.
The checked-in final sources, not this bootstrap helper, reproduce that diff.
"""
import json,os,shutil,subprocess
from pathlib import Path
ROOT=Path('/home/steve/llm-optimizations');BASE=ROOT/'experiments/own-xpu-runtime'
P=BASE/'stage2/packet139-record-bundle';OLD=P.with_name('packet137-token-input')
def links(p):
 return dict(x.split('\t',1) for x in subprocess.check_output(['find',str(p),'-type','l','-printf','%P\t%l\n'],text=True,stdin=subprocess.DEVNULL).splitlines())
def main():
 assert not P.exists() and shutil.disk_usage('/').free>=25_000_000_000
 before=links(OLD)
 def ignore(path,names):
  rel=Path(path).relative_to(OLD)
  return [n for n in names if n in ('__pycache__','build') or rel==Path('.') and n in ('evidence','selections') or rel==Path('v5') and n=='evidence']
 shutil.copytree(OLD,P,symlinks=True,ignore=ignore)
 for name,target in before.items():
  dest=P/name;dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.is_symlink():dest.symlink_to(target)
 assert links(P)==before
 print('All',len(before),'parent symlinks preserved')
if __name__=='__main__':
 import resource
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 main()
