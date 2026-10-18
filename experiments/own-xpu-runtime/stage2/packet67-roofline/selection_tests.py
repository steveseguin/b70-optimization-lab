#!/usr/bin/env python3
"""Actual host submission ABI and parser; no CPU model or device execution."""
import copy,json,subprocess,resource
from build_engine import P,B,ROOT,sha,save,limits
from prepare_views import CHOICES
def main():
 limits();resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3))
 source=P/'submit_fixture.cpp';commands=json.loads((P/'engine-commands.json').read_text())
 cc=next(r['command'] for r in commands if r['name']=='gnu-host-entry-main');cc=cc[:cc.index('-o')]+['-o',str(B/'submit-fixture.o'),'-c',str(source)]
 link=list(next(r['command'] for r in commands if r['name']=='gnu-host-link'))
 link=[x for x in link if not x.endswith('own-rt-iq3-entry.cpp.o')]
 link=[str(B/'submit-fixture.o') if x==str(B/'gnu-host/entry-main.o') else x for x in link];link[link.index('-o')+1]=str(B/'submit-fixture')
 with (B/'submit-fixture-compile.log').open('w') as log:
  for cmd in (cc,link):subprocess.run(cmd,check=True,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT)
 deps=subprocess.check_output(['readelf','-d',str(B/'submit-fixture')],text=True).lower();assert not any(x in deps for x in ('libsycl','libze_loader','libur_loader','libopencl'))
 proof=subprocess.run([str(B/'submit-fixture')],check=True,stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=30)
 rows=[];cases=[(name,(P/'selections'/name/'selection.json').read_text(),None,True) for name in CHOICES]
 good=json.loads(cases[0][1])
 for name,change in [('bad-hc',lambda x:x['choices'].update(hc_a_gate='free-order')),('bad-head',lambda x:x['choices'].update(recurrence_head='rows16')),('bad-target',lambda x:x['choices'].update(route='production')),('missing',lambda x:x['choices'].pop('hc_f_gate')),('extra',lambda x:x['choices'].update(kv='fp8')),('missing-draft',lambda x:x['draft'].pop('gate_up'))]:
  bad=copy.deepcopy(good);change(bad);cases.append((name,json.dumps(bad),None,False))
 raw=json.dumps(good);cases.extend([('duplicate',raw.replace('"hc_a_gate": "production"','"hc_a_gate": "production", "hc_a_gate": "stream4"'),None,False),('trailing',raw+'x',None,False),('bad-hash',raw,'0'*64,False),('missing-hash',raw,'',False)])
 path=B/'selection-test.json'
 for name,text,digest,valid in cases:
  path.write_text(text);r=subprocess.run([str(B/'submit-fixture'),str(path),sha(path) if digest is None else digest],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=10)
  assert (r.returncode==0)==valid,(name,r.stderr);rows.append(dict(name=name,accepted=valid))
 save(P/'evidence/selection-tests.json',dict(passed=True,device_executed=False,cpu_model_executed=False,cases=rows,compile=cc,link=link,binary_sha256=sha(B/'submit-fixture'),source_sha256=sha(source),driver_sha256=sha(P/'selection_tests.py'),build_receipt_sha256=sha(P/'build-device-receipt.json'),actual_submitters=proof.stdout.strip()))
 print(len(rows),'parser cases and actual submitters PASS')
if __name__=='__main__':main()
