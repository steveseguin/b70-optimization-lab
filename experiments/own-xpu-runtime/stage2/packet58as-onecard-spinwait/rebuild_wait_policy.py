"""packet58asd: one serialized compile turn for the CLI wait-policy option.

Same commands as build_engine.py for the three own-rt-iq3 builds and both wait
tests. The K1 fixture wrapper/core and the device-define preparation probe are
NOT rebuilt or rerun: K1 is the unchanged inherited fixture, and the probe is
bracket-binary evidence. The bracket binaries stay byte-identical in
build/bracket/ for comparison and old-binary refusal tests.
"""
import json,resource,shutil,sys
from pathlib import Path
import build_engine as E
P=E.P;B=E.B;ROOT=E.ROOT
BRACKET={'build/device/own-rt-iq3':'83abf236dcfe73bc9da6309fdc1a0c523aab104faa3adcabee3d5589f0b0b1d2',
 'build/gnu-host/own-rt-iq3':'7afd610a549e30c7a97938deae0b8cce3df2aecdb5096fe2c919b7cb2d31a524',
 'build/intel-host/own-rt-iq3':'51849ddd3ea65980ce7b23893d76c7268c798150d2f15abf9ffa0f1f9f2b26ca'}
def main():
 E.limits()
 for n,h in BRACKET.items():
  kept=B/'bracket'/Path(n).relative_to('build')
  assert E.sha(kept)==h,('bracket copy differs',n)
 shutil.copytree(P/'native/generated',B/'native',dirs_exist_ok=True)
 old=str(P.parent/'packet58ag-onecard-ports');original=json.loads((P/'lineage/58ag-build-commands.json').read_text());commands=[]
 with E.compiler_turn():
  E.held=True
  for mode in ('gnu-host','device','intel-host'):
   (B/mode).mkdir(parents=True,exist_ok=True)
   source_mode='gnu-host' if mode=='intel-host' else mode
   names=[source_mode+'-entry-main']+(['device-single_device'] if mode=='device' else [])+[source_mode+'-own-rt-iq3']
   for name in names:
    row=next(r for r in original if r['name']==name);cmd=[x.replace(old,str(P)) for x in row['command']]
    if mode=='intel-host':
     cmd[0]='/opt/intel/oneapi/compiler/2026.0/bin/icpx'
     for flag in ('-o','-MF'):
      if flag in cmd:cmd[cmd.index(flag)+1]=cmd[cmd.index(flag)+1].replace('/gnu-host/','/intel-host/')
     if '-c' not in cmd:cmd=[x.replace(str(B/'gnu-host/entry-main.o'),str(B/'intel-host/entry-main.o')) for x in cmd]
    E.run(cmd,name.replace(source_mode,mode));commands.append(dict(name=name.replace(source_mode,mode),command=cmd))
  for compiler,tag in [('/usr/bin/g++','gnu'),('/opt/intel/oneapi/compiler/2026.0/bin/icpx','intel')]:
   E.run([compiler,'-std=c++20','-O2',P/'native/wait_test.cpp','-o',B/(tag+'-wait-test')],tag+'-wait-build');E.run([B/(tag+'-wait-test')],tag+'-wait-test')
  E.held=False
 artifacts={str(f.relative_to(P)):E.sha(f) for f in B.glob('*/own-rt-iq3') if f.parent.name!='bracket'}
 assert set(artifacts)==set(BRACKET) and all(artifacts[n]!=BRACKET[n] for n in BRACKET)
 E.save(P/'evidence/build.json',dict(passed=True,device_executed=False,revision='packet58asd',commands=commands,artifacts=artifacts,
  bracket_native=[dict(name=n,parent_relpath=str((B/'bracket'/Path(n).relative_to('build')).relative_to(ROOT)),parent_digest=h) for n,h in BRACKET.items()],
  unchanged_k1_fixture=dict(name='build/device/p58-cache-fixtures',parent_relpath=str((B/'device/p58-cache-fixtures').relative_to(ROOT)),parent_digest=E.sha(B/'device/p58-cache-fixtures')),
  source_patch=dict(name='chain-interface.patch',parent_relpath=str((P/'chain-interface.patch').relative_to(ROOT)),parent_digest=E.sha(P/'chain-interface.patch')),
  wait_tests=['gnu','intel'],k1_rebuilt=False,preparation_probe_rerun=False,compile_turns=1,
  peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024))
 print('PASS one compile turn: three own-rt-iq3 rebuilds and both wait tests',artifacts)
if __name__=='__main__':
 sys.modules['rebuild_wait_policy']=sys.modules[__name__];main()
