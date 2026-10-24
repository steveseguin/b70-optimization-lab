#!/usr/bin/env python3
"""Read-only actual metadata joins; never opens raw bundles or archives."""
from pathlib import Path
import gzip,hashlib,importlib.util,json
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('remaining_fixed_raw',P/'reuse.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def main():
 old=(P.parent/'dense-prompt01-canonical/reuse.py').read_text();new=(P/'reuse.py').read_text()
 for name,next_name in [('review_pin','raw_held'),('raw_held','descriptors'),('descriptors','hashes'),('hashes','verify'),('verify','release'),('release','main')]:
  def body(s):return s[s.index('def '+name+'('):s.index('def '+next_name+'(')]
  assert body(old)==body(new),'filesystem/release machinery changed '+name
 expected=tuple(f'prompt-{i:02d}-{mode}/rank{rank}/state-2147483647/state.bundle' for i in range(2,12) for mode in ('none','mtp') for rank in (0,1))
 assert A.NAMES==expected and len(set(A.NAMES))==40
 first=A.authority(0);rows=A.mapping();assert first==rows[expected[0]]
 for bad in [-1,40,True,'0']:
  try:A.authority(bad)
  except (ValueError,TypeError):pass
  else:raise AssertionError('invalid batch accepted')
 appraisal=json.loads(A.APPRAISAL.read_text());authorities=appraisal['authority_sha256']
 prior_review=next(A.R/f for f in authorities if f.endswith('/review.json'));prior=json.loads(prior_review.read_text())
 assert prior['passed'] and prior['all12_exact'] and A.sha(prior_review)=='4e97f8a533de01c64d299582e8cdb884bb1979f7e2a405bd5794f36f4869294b'
 index=next(A.R/f for f in authorities if f.endswith('artifact-index.jsonl.gz'));prior_rows={}
 with gzip.open(index,'rt') as f:
  for line in f:
   x=json.loads(line)
   if x['root']=='evidence' and x['path'] in rows:
    assert x['path'] not in prior_rows;prior_rows[x['path']]=x
 assert set(prior_rows)==set(rows)
 inventory=json.loads(next(A.R/f for f in authorities if f.endswith('/complete.json')).read_text());assert inventory['passed'] and inventory['all_four_phases_passed'];bybatch={x['batch']:x for x in inventory['batches']}
 for name,row in rows.items():
  actual=prior_rows[name];assert (actual['bytes'],actual['sha256'])==(row['bytes'],row['raw_sha256'])
  archive=bybatch[row['canonical_batch']];assert (archive['name'],archive['source_bytes'],archive['usb'],archive['archive_bytes'],archive['archive_sha256'])==(name,row['bytes'],row['canonical_archive'],row['canonical_archive_bytes'],row['canonical_archive_sha256'])
 assert sum(x['bytes'] for x in rows.values())==4434863360
 print(json.dumps(dict(passed=True,source_only=True,actual_metadata_rows=40,recoverable_bytes=4434863360,unchanged_filesystem_functions=6,invalid_batches_refused=4,new_review_sha256=json.loads(A.BINDING.read_text())['review']['sha256'],prior_review_sha256=A.sha(prior_review),payload_read=False,operations=False),indent=2))
if __name__=='__main__':main()
