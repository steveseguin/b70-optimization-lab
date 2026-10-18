"""CPU regression replay of packet128's intrusive trace, never new device data.

The parent predates queue tags: routes here are inferred from known call sites.
This proves the old overlap no longer asserts and the old slowdown still blocks
ranking. It cannot measure packet128b overhead or prove its recording coverage.
"""
import importlib.util,json,resource
from pathlib import Path
from unittest.mock import patch
from build_engine import P,ROOT,sha,save,limits
import analyze

def main():
 limits();old=P.with_name('packet128-attribution')/'evidence/device-B'
 identity=json.loads((old/'identity.json').read_text())
 def inherited_sha(path):
  if Path(path)==P/'build/device/own-rt-iq3':return identity['binary_sha256']
  return sha(path)
 def sampled_events(path):
  with path.open() as f:
   for s in f:
    e=json.loads(s)
    if not e.get('schema','').startswith('packet128.') or not 9<=e['fixture']<=16:continue
    e['schema']=e['schema'].replace('packet128.','packet128b.')
    if e['schema']=='packet128b.event.v1':
     copy='transfer' in e['label']
     e.update(queue='copy-auto' if copy else 'compute',queue_kind='copy' if copy else 'compute')
    yield e
 with patch.object(analyze,'sha',side_effect=inherited_sha),patch.object(analyze,'events',side_effect=sampled_events):r=analyze.generate(old)
 assert not r['ranking_usable'] and not r['levers']
 save(P/'evidence/parent-reanalysis.json',dict(passed=True,device_executed=False,
  parent_trace_only=True,queue_labels_inferred_not_observed=True,sampling_applied_after_recording=True,
  packet128b_speed_measured=False,class_balanced_tps=r['summary']['class_balanced_tps'],
  ratio_to_baseline=r['summary']['ratio_to_baseline'],overhead_bounded=False,ranking_withheld=True,
  sampled_cycles=r['cycles'],all_prediction_cycles=r['all_prediction_cycles'],coverage=r['coverage'],omitted=r['omitted'],
  parent_receipt_sha256=r['receipt_sha256'],sources={str(f.relative_to(ROOT)):sha(f) for f in (P/'parent_reanalysis.py',P/'analyze.py')}))
 print('Old trace replay: queue overlap accepted, complete sampled cycles',r['cycles'],'; old throughput',r['summary']['class_balanced_tps'],'still fails overhead gate')
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
