#!/usr/bin/env python3
"""Build from packet56's verified read-only mirror. CPU compilation only."""
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys

P=Path(__file__).resolve().parent
ROOT=P.parents[3]
PARENT=P.parent/'packet56-draft-prefix'
B=P/'build'
MIRROR=PARENT/'build/checked'
LOCAL=B/'engine'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 assert os.environ.get('OMP_NUM_THREADS')=='2'
 assert not (P/'screen-seal.json').exists(), 'sealed: do not rebuild'
 LOCAL.mkdir(parents=True,exist_ok=True)
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 commands=[];sources={};artifacts={}
 def bind(path):sources[str(path.relative_to(ROOT))]=sha(path)
 def run(cmd,name):
  cmd=list(map(str,cmd));commands.append(dict(command=cmd,cwd=str(ROOT),name=name))
  with (B/(name+'.log')).open('w') as out:subprocess.run(cmd,cwd=ROOT,stdout=out,stderr=subprocess.STDOUT,check=True)
  print(name,'PASS',flush=True)
 # Retain and rerun the existing primitive gate, including actual SYCL compile.
 run([sys.executable,'-B',P/'build.py'],'primitives')
 primitive=json.loads((P/'build-device-receipt.json').read_text())
 save(P/'primitive-build-receipt.json',primitive)
 sources.update(primitive['sources'])
 sys.path.insert(0,str(PARENT))
 from submission_overlay import apply_submission_overlay
 local_names=('main.cpp','p60_submit.cpp','p60_submit.hpp','p60_math.hpp','p60_kernels.hpp')
 for name in local_names:
  src=P/name;bind(src)
  text=apply_submission_overlay(src,src.read_text())
  def include(m):
   if m[1] in local_names:target=LOCAL/m[1]
   else:
    options=[PARENT/m[1],PARENT.parents[1]/'stage1/packet3-prep/src'/m[1],PARENT.parent/'packet2/kernels'/m[1],PARENT.parent/'packet2/loader'/m[1]]
    original=next(x.resolve() for x in options if x.is_file())
    if original.name=='kernel_guard.hpp':target=original
    else:target=MIRROR/original.relative_to(ROOT)
    assert target.is_file(),target
   return '#include '+json.dumps(str(target))
  text=re.sub(r'^\s*#include\s*"([^"\n]+)"',include,text,flags=re.M)
  # Keep the existing model constants and draft manifest at their sealed paths.
  if name=='main.cpp':text=text.replace('fs::path(__FILE__).parent_path()', 'fs::path('+json.dumps(str(PARENT))+')')
  (LOCAL/name).write_text(text)
 (LOCAL/'entry-main.cpp').write_text('#define main packet26_model_entry\n#include "main.cpp"\n#undef main\n')
 for mode in ('gnu-host','device'):
  pb=PARENT/'build'/mode;dest=B/mode;dest.mkdir(exist_ok=True)
  receipt_path=PARENT/('build-'+mode+'-receipt.json');receipt=json.loads(receipt_path.read_text());bind(receipt_path)
  # Verify all inherited source and generated mirror bytes against their build.
  for name,digest in receipt['compiled_sources_sha256'].items():
   path=ROOT/name;assert sha(path)==digest, name;bind(path)
  for name,digest in receipt['checked_mirror_sha256'].items():
   path=PARENT/'build'/name;assert sha(path)==digest,name;bind(path)
  cc=pb/'compile_commands.json';assert sha(cc)==receipt['compile_commands_sha256'];bind(cc)
  compilation=json.loads(cc.read_text())
  command=next(x for x in compilation if x['file']==str(pb/'entry-main.cpp'))
  base=shlex.split(command['command']);base=base[:base.index('-o')]
  for stem in ('entry-main','p60_submit'):
   run([*base,'-o',dest/(stem+'.o'),'-c',LOCAL/(stem+'.cpp')],mode+'-'+stem)
  link=pb/'CMakeFiles/own-rt-iq3.dir/link.txt';bind(link)
  assert sha(link)==receipt['link_files_sha256'][str(link.relative_to(PARENT/'build'))]
  args=shlex.split(link.read_text());out=args.index('-o');args[out+1]=str(dest/'own-rt-iq3')
  for i,arg in enumerate(args):
   if arg.endswith('.o'):
    if arg=='CMakeFiles/programs.dir/entry-main.cpp.o':args[i]=str(dest/'entry-main.o')
    else:
     path=pb/arg
     if not path.is_file():
      # The coordinator reclaimed parent .o files. Rebuild only link inputs
      # into this packet using the exact parent commands and checked sources.
      entry=next(x for x in compilation if shlex.split(x['command'])[shlex.split(x['command']).index('-o')+1]==arg)
      compile_args=shlex.split(entry['command']);path=dest/'inherited'/arg
      path.parent.mkdir(parents=True,exist_ok=True)
      compile_args[compile_args.index('-o')+1]=str(path)
      bind(Path(entry['file']))
      if not path.exists():run(compile_args,mode+'-inherited-'+str(i))
     bind(path);args[i]=str(path)
  args.insert(out,str(dest/'p60_submit.o'))
  run(args,mode+'-link')
  artifacts[str((dest/'own-rt-iq3').relative_to(P))]=sha(dest/'own-rt-iq3')
 for name in (*local_names,'entry-main.cpp'):bind(LOCAL/name)
 for name in ('build.py','build_engine.py'):bind(P/name)
 bind(PARENT/'mtp-manifest.tsv')
 for path in (P/'commands.json',P/'primitive-build-receipt.json'):bind(path)
 save(P/'engine-commands.json',commands);bind(P/'engine-commands.json')
 # Catch concurrent source/object changes across the build, not just before it.
 for name,digest in sources.items():assert sha(ROOT/name)==digest,name
 # Parent build/ is an external-results symlink. Preserve the exact compiler
 # input bytes here so the screen's repository-bound source seal stays closed.
 # These are snapshots of inputs actually compiled above, not replacement
 # source claims. Record and rehash both the original and its retained copy.
 external={};sealed_sources={}
 for name,digest in sources.items():
  original=ROOT/name
  if original.resolve().is_relative_to(ROOT):sealed_sources[name]=digest
  else:
   snapshot=P/'evidence/inherited-build-inputs'/name
   snapshot.parent.mkdir(parents=True,exist_ok=True);snapshot.write_bytes(original.read_bytes())
   assert sha(original)==digest and sha(snapshot)==digest,name
   relative=str(snapshot.relative_to(ROOT));sealed_sources[relative]=digest
   external[name]=dict(resolved=str(original.resolve()),snapshot=relative,sha256=digest)
 save(P/'build-device-receipt.json',dict(schema='packet60.lean-engine-build.v1',passed=True,
  device_executed=False,engine_integrated=True,sources=sealed_sources,artifacts=artifacts,
  external_compiler_inputs=external,
  inherited_objects='unchanged packet56 compiler inputs rebuilt locally when parent objects are absent',
  nice=19,cpu_affinity=sorted(os.sched_getaffinity(0))))
 print('CPU and SYCL engines built; no device binary executed',flush=True)
if __name__=='__main__':main()
