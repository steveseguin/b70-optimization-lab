"""Prepare only packet190; retain parent evidence as historical inputs."""
import json,os,shutil,hashlib,resource
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];P=ROOT/'experiments/own-xpu-runtime/stage2/packet190-record-bundle-k3x';OLD=P.with_name('packet136-record-bundle');S=P.with_name('packet153-snapshot-host')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,row):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(row,indent=2)+'\n')
def main():
 assert shutil.disk_usage('/').free-35_000_000>=30_000_000_000
 source=O.with_name('packet136-orchestration')
 for f in source.glob('*.py'):
  if f.name not in ('copy_bundle.py','verify_ready.py'):
   (O/f.name).write_text(f.read_text().replace('packet136-record-bundle','packet190-record-bundle-k3x').replace('packet136-orchestration','packet190-orchestration'))
 for name in ('inputs','oracle-authority'):
  shutil.copytree(source/name,O/name,symlinks=True,dirs_exist_ok=True)
 for f in (O/'inputs').rglob('*'):
  if f.is_file() and f.suffix=='.json' and f.name not in ('packet136-copy.json','packet153-native.json'):
   f.write_text(f.read_text().replace('packet136-record-bundle','packet190-record-bundle-k3x').replace('packet136-orchestration','packet190-orchestration'))
 for name in ('coverage.json','engine-commands.json','dependency-pins.json','shared-wrapper-pin.json','runtime-revision.json','startup103.json','chain-binding.json','screen-seal.json','baseline-pins.json','extension-slots.json','fixed-base.json'):
  shutil.copy2(OLD/name,P/name)
 # Required immutable legacy fixture binaries remain bound to their exact bytes.
 parent=json.loads((OLD/'build-receipt.json').read_text());save(O/'inputs/packet136-chain-seal.json',parent)
 links={}
 for name,digest in parent['artifacts_sha256'].items():
  if name in ('device/own-rt-iq3','gnu-host/own-rt-iq3'):continue
  source=OLD/'build'/name;dest=P/'build'/name
  assert sha(source)==digest,(name,'parent artifact changed')
  dest.parent.mkdir(parents=True,exist_ok=True)
  if not dest.exists():dest.symlink_to(source.resolve())
  links[name]=digest
 for name in ('input','fusion-fixtures'):
  shutil.copytree(OLD/'build'/name,P/'build'/name,symlinks=True,dirs_exist_ok=True)
 save(O/'inputs/inherited-artifacts.json',links)
 # Vendor all packet153 native headers used by the bound executable.
 shutil.copytree(S/'v5/native',P/'snapshot-static/native',symlinks=True,dirs_exist_ok=True)
 bind=json.loads((O/'inputs/packet153-native.json').read_text())
 for f in (P/'snapshot-static').rglob('*'):
  if f.is_file():bind['sources'][str(f.relative_to(P))]=sha(f)
 for compiler in ('GNU','Intel'):
  for kind in ('state','real-shape'):
   src=S/'v5/build'/kind/('fixture-'+compiler);dst=P/'build/cpu'/kind/src.name;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
   bind['binaries'][str(dst.relative_to(P))]=dict(sha256=sha(dst),origin=str(src.relative_to(ROOT)))
 for mode in ('production','static'):
  shutil.copy2(S/'v5/build/state'/(mode+'.json'),P/'build/cpu/state'/(mode+'.json'))
 save(O/'inputs/packet153-native.json',bind)
 choice=json.loads((OLD/'bundle-selection.json').read_text());choice['snapshot_host']='static';save(P/'bundle-selection.json',choice)
 selection=json.loads((OLD/'selection.json').read_text());selection['choices'].update(probe='off',snapshot_host='static');save(P/'selection.json',selection)
 assert selection==json.loads((S/'v5/lineage/static/selection.json').read_text())
 save(P/'chain-registration.json',dict(output='device-cards01-p190-a'))
 shutil.copy2(S/'v5/lineage/static/memory-plan.json',P/'memory-plan.json')
 save(O/'inputs/packet153-memory.json',json.loads((P/'memory-plan.json').read_text()))
 for name in ('prepare_submission.py','submission_evidence.py','submission.py'):
  src=O.with_name('packet136s-submission')/name
  (O/name).write_text(src.read_text().replace('packet136-record-bundle','packet190-record-bundle-k3x'))
 text=(O.with_name('packet136-orchestration')/'device-entry.sh').read_text().replace('packet136-record-bundle','packet190-record-bundle-k3x').replace('device-cards01-a','device-cards01-p190-a')
 (O/'device-entry.sh').write_text(text)
 print('Prepared packet190 inputs; free bytes',shutil.disk_usage('/').free)
if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
