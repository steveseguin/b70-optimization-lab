"""Diagnostic provenance only. Runtime safety and exactness remain mandatory."""
import json
from pathlib import Path
MARKERS=dict(diagnostic_unsealed=True,qualifying=False)
def reject_nonqualifying(value):
 if isinstance(value,dict):
  if value.get('diagnostic_unsealed') or value.get('qualifying') is False:
   raise ValueError('diagnostic/unqualified receipt cannot be submitted, published or promoted')
  for child in value.values():reject_nonqualifying(child)
 elif isinstance(value,list):
  for child in value:reject_nonqualifying(child)
def actual_artifacts(build,root,sha):
 result={}
 for name in build['artifacts_sha256']:
  path=Path(name)
  if path.is_absolute() or len(path.parts)!=2 or '..' in path.parts:raise ValueError('invalid artifact path')
  result[name]=sha(root/path)
 if not result:raise ValueError('empty artifact inventory')
 return result
def label_outputs(root,record,sha):
 """Annotate completed receipt/summary outputs before final hash retention.

 Native binary receipts are immutable while their owners are running. Raw event
 streams, dispatch tables, tensor bytes and exactness oracles are not rewritten.
 """
 for path in root.rglob('*.json'):
  if path.is_symlink() or path.name.startswith('dispatch-'):continue
  # Census and binary metadata are not performance/qualification receipts.
  if not any(word in path.name for word in ('receipt','summary','result','metrics','timing','class-times','window','ownership','teardown','failure','launch','admission')):continue
  value=json.loads(path.read_text())
  if isinstance(value,dict):
   value.update(MARKERS)
   path.write_text(json.dumps(value,indent=2)+'\n')
 record.update(MARKERS,diagnostic=True,diagnostic_for_speed=True)
 if isinstance(record.get('summary'),dict):record['summary'].update(MARKERS)
 for name in record.get('receipts',{}):
  path=root/name
  if path.is_file():record['receipts'][name]=sha(path)
 if 'summary_sha256' in record:record['summary_sha256']=sha(root/'run0/summary.json')
