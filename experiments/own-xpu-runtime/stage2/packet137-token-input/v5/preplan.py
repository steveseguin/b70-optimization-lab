"""Non-circular pre-plan prerequisites; queue success/failure is sealed afterward."""
from common import HERE,ROOT,read,require,verify_map,sha
GATES=('argument-gate','legacy-windows','all-windows','worker-gate','launch-limits','report137b-gate')
def verify():
 for name in GATES:
  row=read(HERE/'evidence'/(name+'.json'))
  require(row.get('passed') is True and row.get('device_executed') is False,'missing pre-plan CPU gate '+name)
  if row.get('sources'):verify_map(ROOT,row['sources'])
 require(read(HERE/'evidence/legacy-windows.json')['total_windows']==44,'all token_input constructors required')
 require(read(HERE/'evidence/all-windows.json')['real_queue_loop'],'real queue-loop checks required')
 binaries=read(HERE/'evidence/legacy-windows.json')['external_legacy_binaries']
 expected={str((HERE.parents[1]/'packet136-record-bundle/build/gnu-host'/name).relative_to(ROOT)) for name in ('k2-fixtures','p49d-fixtures')}
 require(set(binaries)==expected,'legacy binary scope changed')
 for name,proof in binaries.items():
  path=ROOT/name
  require(path.is_symlink() and str(path.readlink())==proof['link'] and str(path.resolve())==proof['resolved'],'legacy binary link changed')
  require(sha(path)==proof['sha256'],'legacy binary bytes changed')
 return True
