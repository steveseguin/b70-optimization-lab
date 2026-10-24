#!/usr/bin/env python3
"""Metadata-only source/authority smoke; no raw/archive descriptors opened."""
from pathlib import Path
import importlib.util,json
P=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('fixed16_metadata',P/'reuse.py');A=importlib.util.module_from_spec(s);s.loader.exec_module(A)
def main():
 # Authority reads only pinned JSON/JSONL/seals; explicitly make payload seams
 # fail if accidentally invoked during this smoke.
 def forbidden(*a,**k):raise AssertionError('payload/operation invoked in metadata smoke')
 A.C.compressed=forbidden;A.C.members=forbidden;A.C.held=forbidden;A.raw_held=forbidden
 row=A.authority(0);b=json.loads(A.BINDING.read_text());assert len(A.EXPECTED)==16 and len(set(A.EXPECTED))==16;assert row['raw_path']==A.EXPECTED[0]
 counts={}
 for x in b['rows']:counts[x['profile']]=counts.get(x['profile'],0)+1
 assert counts=={'dense-q6':6,'class-a-failed':4,'class-b':6}
 assert sum(x['bytes'] for x in b['rows'])==1773945344
 for bad in [-1,16,True,'0']:
  try:A.authority(bad)
  except (ValueError,TypeError):pass
  else:raise AssertionError('invalid batch accepted')
 for name in ['verify','release','hashes','review_pin']:assert getattr(A.M,name).__code__.co_filename==str(A.PARENT)
 assert A.M.__file__==A.__file__ and A.M.P==A.P and A.M.BINDING_SHA==A.BINDING_SHA
 assert all(x['failed_run_stays_failed']==(x['profile']=='class-a-failed') for x in b['rows'])
 print(json.dumps(dict(passed=True,metadata_only=True,paths=16,recoverable_bytes=1773945344,profile_counts=counts,invalid_batches_refused=4,unchanged_parent_verification_release_functions=True,raw_or_archive_payload_read=False,operations=False),indent=2))
if __name__=='__main__':main()
