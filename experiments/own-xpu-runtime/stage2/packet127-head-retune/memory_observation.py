"""Passive own-process memory evidence; no device discovery or device opens."""
import json,re
from pathlib import Path
from memory_gate import snapshot

def clients(raw):
 rows={}
 for fd,lines in raw['drm_fdinfo'].items():
  fields=dict(line.split(':',1) for line in lines if ':' in line)
  key=(fields.get('drm-pdev','').strip(),fields.get('drm-client-id','').strip())
  if not all(key):continue
  values={}
  for name,value in fields.items():
   if not name.startswith(('drm-total-vram','drm-resident-vram','drm-total-system','drm-resident-system')):continue
   m=re.fullmatch(r'\s*(\d+)(?:\s+(KiB|MiB|GiB|B))?\s*',value)
   if m:values[name]=int(m[1])*{None:1,'B':1,'KiB':1024,'MiB':1024**2,'GiB':1024**3}[m[2]]
  if key in rows:rows[key]['fds'].append(fd)
  else:rows[key]=dict(pci=key[0],client_id=key[1],fds=[fd],bytes=values)
 return list(rows.values())

def capture(transport,output,phase):
 rows=[]
 for rank,child in enumerate(transport.children):
  raw=snapshot(child.pid);raw['phase']=phase
  path=transport.out/f'rank{rank}/census.json';arena=json.loads(path.read_text())
  rows.append(dict(rank=rank,allocator_device_bytes=arena['totals']['device'],process=raw,unique_clients=clients(raw)))
 result=dict(phase=phase,ranks=rows,device_nodes_opened=False,global_device_free_bytes=None,interpretation='Allocator requests and per-client DRM residency are different counters. Duplicate fd client IDs are deduplicated; clients/cards are not summed into global free memory. Driver/library pools outside the arena are not inferred.')
 (Path(output)/f'memory-{phase}.json').write_text(json.dumps(result,indent=2)+'\n')
 return result

def validate(observation,phase,admission,pci):
 assert observation['phase']==phase and observation['device_nodes_opened'] is False
 assert [r['rank'] for r in observation['ranks']]==[0,1]
 assert [r['rank'] for r in admission['ranks']]==[0,1]
 for rank,row in enumerate(observation['ranks']):
  raw=row['process'];expected=admission['ranks'][rank]
  assert raw['phase']==phase and not raw.get('process_exited')
  assert raw['pid']==expected['process']['pid']
  assert row['allocator_device_bytes']==expected['device_allocation_bytes']
  actual=clients(raw);assert row['unique_clients']==actual and actual
  selected=[r for r in actual if r['pci']==pci[rank]]
  assert selected,'mapped rank device missing from memory evidence'
  assert all(r['pci'] in pci for r in actual),'foreign card in memory evidence'
  # Require observable byte counters, not merely an empty fdinfo key. Keep
  # possible paging visible; residency need not equal requested allocations.
  assert any(any(k.startswith('drm-total-vram') and v>0 for k,v in r['bytes'].items()) and any(k.startswith('drm-resident-vram') and v>0 for k,v in r['bytes'].items()) for r in selected),'VRAM counters unavailable'
 return True
