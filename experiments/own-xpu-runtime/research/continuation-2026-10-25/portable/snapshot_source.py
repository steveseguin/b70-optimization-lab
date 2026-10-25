#!/usr/bin/env python3
"""Read-only Git object export; no checkout/branch or live source bytes used."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import subprocess

PREFIX='experiments/own-xpu-runtime/engine'
SUPPORT='experiments/own-xpu-runtime/gsq-rco-iq3s/integration/host-support/device_validation.hpp'

def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,required=True);p.add_argument('--commit',required=True)
 p.add_argument('--snapshot',type=Path,required=True);p.add_argument('--archive',type=Path,required=True);p.add_argument('--extract',type=Path,required=True)
 a=p.parse_args();repo=a.repo.resolve();snapshot=a.snapshot.absolute();archive=a.archive.absolute();extract=a.extract.absolute()
 def git(*args):return subprocess.check_output(['git','-C',str(repo),*args])
 commit=git('rev-parse',a.commit+'^{commit}').decode().strip()
 if any(x.exists() for x in (snapshot,archive,Path(str(archive)+'.manifest.json'),extract)):raise ValueError('fresh snapshot/archive/extract required')
 paths=git('ls-tree','-rz','--name-only',commit,'--',PREFIX,SUPPORT).decode().split('\0');paths=[x for x in paths if x]
 files={}
 for name in paths:
  rel=PurePosixPath(name).relative_to(PREFIX) if name.startswith(PREFIX+'/') else None
  if name!=SUPPORT and not (str(rel) in ('README.md','build.py','build-manifest.json') or rel.parts[0] in ('src','planning','release','deployment','profiles')):continue
  mode=git('ls-tree',commit,'--',name).decode().split()[0]
  if mode not in ('100644','100755'):raise ValueError('nonregular committed source: '+name)
  files[name]=git('show',commit+':'+name)
 snapshot.mkdir()
 for name,data in files.items():
  path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
 spec=importlib.util.spec_from_file_location('frozen_bundle',snapshot/PREFIX/'release/source_bundle.py');bundle=importlib.util.module_from_spec(spec);spec.loader.exec_module(bundle)
 # The frozen bundler's Git reads are fulfilled from this exact commit. It still
 # compares every snapshot input byte to the original committed blob and checks
 # include closure; no checkout or temporary Git branch is involved.
 def frozen_git(root,*args):
  if args==('rev-parse','--show-toplevel'):return (str(snapshot)+'\n').encode()
  if args==('rev-parse','HEAD'):return (commit+'\n').encode()
  if args[:3]==('ls-files','-z','--'):return b'\0'.join(x.encode() for x in paths if x.startswith(args[3]+'/'))+b'\0'
  if args[:3]==('ls-files','--error-unmatch','--'):
   if args[3] not in files:raise ValueError('missing committed supplemental source')
   return (args[3]+'\n').encode()
  if args[0]=='show' and args[1].startswith(commit+':'):return git(*args)
  raise ValueError('unexpected frozen Git query: '+repr(args))
 bundle.git=frozen_git
 contents,report=bundle.prepare(snapshot/PREFIX)
 data=bundle.archive_bytes(contents)
 if report['source_commit']!=commit:raise ValueError('source commit mismatch')
 archive.write_bytes(data);report['archive']={'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data)}
 Path(str(archive)+'.manifest.json').write_bytes(bundle.json_bytes(report))
 extract.mkdir()
 for name,payload in contents.items():
  path=extract/'own-xpu-runtime-source'/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(payload)
 # Verify extracted contents independently against the returned manifest.
 for row in report['files']:
  path=extract/'own-xpu-runtime-source'/row['path']
  if hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('extract hash mismatch')
 result=dict(source_commit=commit,archive=str(archive),archive_sha256=report['archive']['sha256'],archive_bytes=len(data),
  extracted_source=str(extract/'own-xpu-runtime-source'),files=len(contents),source_bytes_from_live_worktree=0,
  snapshot_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),device_execution=False)
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
