"""Preserve every parent link verbatim, including oracle authority; no dereference."""
import json,os,resource
from pathlib import Path
P=Path(__file__).resolve().parent
BASE=P.with_name('packet136-record-bundle')
def main():
 rows=[]
 for root,dirs,files in os.walk(BASE,followlinks=False):
  for name in dirs+files:
   source=Path(root)/name
   if not source.is_symlink():continue
   relative=source.relative_to(BASE);dest=P/relative;target=os.readlink(source)
   if dest.is_symlink():assert os.readlink(dest)==target
   else:
    assert not dest.exists(),str(dest)
    dest.parent.mkdir(parents=True,exist_ok=True);dest.symlink_to(target)
   rows.append(dict(path=str(relative),target=target))
 (P/'symlinks.json').write_text(json.dumps(dict(parent=str(BASE),count=len(rows),links=rows),indent=2)+'\n')
 print(len(rows),'parent links preserved verbatim; ignored build links reproducible with this script')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
