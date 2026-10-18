"""Non-circular pre-plan prerequisites; queue success/failure is sealed afterward."""
from common import HERE,ROOT,read,require,verify_map
GATES=('argument-gate','legacy-windows','all-windows','worker-gate','launch-limits')
def verify():
 for name in GATES:
  row=read(HERE/'evidence'/(name+'.json'))
  require(row.get('passed') is True and row.get('device_executed') is False,'missing pre-plan CPU gate '+name)
  if row.get('sources'):verify_map(ROOT,row['sources'])
 require(read(HERE/'evidence/legacy-windows.json')['total_windows']==44,'all token_input constructors required')
 require(read(HERE/'evidence/all-windows.json')['real_queue_loop'],'real queue-loop checks required')
 return True
