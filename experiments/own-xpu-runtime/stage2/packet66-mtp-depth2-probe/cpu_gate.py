#!/usr/bin/env python3
"""Two fresh small state fixtures; source identity for every target body."""
import hashlib,json,os,subprocess,resource
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];BASE=P.with_name('packet61x-spin-hcfusion-wait')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 assert os.getpriority(os.PRIO_PROCESS,0)==19
 assert set(os.sched_getaffinity(0))<=set(range(8,16))|set(range(24,32))
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 f=P/'fixture';f.mkdir(exist_ok=True)
 parent=json.loads((P/'parent-source-manifest.json').read_text());same={}
 for name,digest in parent.items():
  if Path(name).suffix not in ('.cpp','.hpp','.inc') or name=='mtp.hpp':continue
  assert sha(P/name)==digest==sha(BASE/name),name;same[name]=digest
 rows=[]
 for arm in ('off','on1','on2'):
  dest=f/arm;assert not dest.exists()
  cmd=[str(P/'build'/('reference-fixture' if arm=='off' else 'probe-fixture')),str(dest),'off' if arm=='off' else 'on']
  result=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
  (f/(arm+'.log')).write_text(result.stdout+result.stderr)
  result.check_returncode()
  rows.append(dict(arm=arm,command=cmd,result=json.loads(result.stdout.splitlines()[-1]),sha256=sha(dest/'state.bin')))
 expected=(f/'off/state.bin').read_bytes()
 assert all((f/arm/'state.bin').read_bytes()==expected for arm in ('on1','on2'))
 assert all((f/arm/'proposals.txt').read_bytes()==(f/'off/proposals.txt').read_bytes() for arm in ('on1','on2'))
 metadata=P.parent/'packet56-draft-prefix/build/input/plan.tsv'
 target=f/'target';target.mkdir()
 cmd=[str(P/'build/target-fixture'),str(target),str(metadata),str(P/'dispatch-speed6.json')]
 result=subprocess.run(cmd,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=120)
 (f/'target.log').write_text(result.stdout+result.stderr);result.check_returncode()
 target_expected=(target/'expected.bin').read_bytes();target_actual=(target/'actual.bin').read_bytes();assert target_expected==target_actual
 assert target_actual==(BASE/'integrated-fixture/actual.bin').read_bytes(),'packet61x target byte identity'
 (f/'expected.bin').write_bytes(expected+target_expected);(f/'actual.bin').write_bytes((f/'on2/state.bin').read_bytes()+target_actual)
 sources={str((P/name).relative_to(ROOT)):sha(P/name) for name in ('probe_fixture.cpp','cpu_gate.py','mtp.hpp','parent-source-manifest.json')}
 sources[str(metadata.relative_to(ROOT))]=sha(metadata);sources[str((BASE/'integrated-fixture/actual.bin').relative_to(ROOT))]=sha(BASE/'integrated-fixture/actual.bin')
 receipt=dict(schema='own-runtime.screen.byte-fixture.v1',passed=True,device_executed=False,changed_class='Recursive draft transaction: all draft mutable bytes, target buffers, next d1 and host position/extent; sync/async, pool/extent boundaries and request reset',command=['python3','-B',str(P/'cpu_gate.py')],build_receipt_sha256=sha(P/'build-device-receipt.json'),sources=sources,expected=dict(path='fixture/expected.bin',sha256=sha(f/'expected.bin')),actual=dict(path='fixture/actual.bin',sha256=sha(f/'actual.bin')),runs=rows,unchanged_target_sources=same,bytes_compared=len(expected))
 (f/'receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('PASS',len(expected),'bytes',len(same),'unchanged target sources')
if __name__=='__main__':main()
