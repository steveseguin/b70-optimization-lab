#!/usr/bin/env python3
"""Run the real mini Engine across position32 under ASAN+UBSAN, CPU only."""
import json
import capacity_cpu_gate as c
c.LEDGER=c.P/'capacity-rollback-asan.json'
binary=c.B/'asan/own-rt-iq3';c.host_binary(binary);sources=c.source_identity()
ledger=json.loads(c.LEDGER.read_text()) if c.LEDGER.exists() else dict(passed=False,device_executed=False,rows=[])
selected=[]
for controller in ('python','native'):
 for mode in ('none','hit','miss'):
  case=dict(name=f'rollback-4096-{controller}-{mode}',phase='rollback',context=4096,mode=mode,controller=controller)
  selected.append(c.run_case(case,'asan',binary,sources,ledger))
ledger.update(passed=len(selected)==6 and all(r['passed'] for r in selected),source_sha256=sources,binary_sha256=c.storage.digest(binary),cases=6,device_executed=False)
c.save(c.LEDGER,ledger)
