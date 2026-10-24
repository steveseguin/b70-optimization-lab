#!/usr/bin/env python3
"""Fixed54 closed Engine-B bundles; canonical verification and separate release."""
from pathlib import Path
import argparse,gzip,hashlib,importlib.util,json
P=Path(__file__).resolve().parent;L=P.parents[1];R=L.parents[2]
PARENT=P.parent/'dense-prompt01-canonical/reuse.py'
PARENT_SHA='51fba80be57bdbdb6693877b30eeea435155f8c6c36b8e90e06e0f719446ef59'
BINDING=P/'closure-binding.json';BINDING_SHA=None
RAW=Path('/mnt/usb-models/own-xpu-runtime-results/gsq-dense-packed-block-engine-b')
REVIEW=L/'dense-packed-block/engine/operating/launch-b/evidence/device-b/review.json'
TERMINAL=Path('/home/steve/own-xpu-runtime-results/gsq-dense-packed-block-engine-b.control/terminal.json')
BINARY='5aef74d5f803b33758711db352ee5e1a393a364e6c33aa9f8a4cdb4478f5fe6a'
PLAN='7fbfc6631213c1577deb2fddf5428bcaf4b4175e3455e9440605894e45682ca9'
CANON_REVIEW=L/'expert-iq3xxs-block/engine/operating/evidence/device-a/review.json'
CANON_REVIEW_SHA='4e97f8a533de01c64d299582e8cdb884bb1979f7e2a405bd5794f36f4869294b'
CANON_COMPLETE=P.parent/'expert-block-closed/evidence/complete.json'
CANON_COMPLETE_SHA='c1abc25e59589e36df8648890b484d7e206b90f14ba78a0885c5f6475a1f6dd1'
PREFIXES=('', 'warmup-none/', 'warmup-mtp/')+tuple(f'prompt-{i:02d}-{mode}/' for i in range(12) for mode in ('none','mtp'))
NAMES=tuple(prefix+f'rank{rank}/state-2147483647/state.bundle' for prefix in PREFIXES for rank in (0,1))
TOTAL=5987065536

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,m):
 if not v:raise ValueError(m)
need(sha(PARENT)==PARENT_SHA,'frozen raw canonical machinery')
s=importlib.util.spec_from_file_location('dense_packed_canonical_private',PARENT);M=importlib.util.module_from_spec(s);s.loader.exec_module(M);C=M.C
M.P=P;M.__file__=__file__;M.RAW=RAW;M.NAMES=NAMES;M.BINDING_SHA=BINDING_SHA
C.DEST=Path('/home/steve/own-xpu-runtime-results/gsq-dense-packed-canonical-a')

def index(path,digest):
 need(sha(path)==digest,'audited physical index identity');rows={}
 with gzip.open(path,'rt') as f:
  for line in f:
   need(len(line)<=16384,'bounded index row');x=json.loads(line)
   if x['root']=='evidence' and x['path'] in NAMES:
    need(x['path'] not in rows,'unique physical bundle');rows[x['path']]=x
 need(set(rows)==set(NAMES),'all54 audited physical payloads');return rows

def closed(review,term):
 need(review['passed'] and review['all12_exact'] and review['bundles']==54 and review['requests']==26 and review['measured_arms']==24 and review['physical_drain'] and review['kernel_fault_baseline_unchanged'],'full closed Engine-B audit')
 need(review['native_binary_sha256']==BINARY and review['plan_sha256']==PLAN,'exact candidate identity')
 budget=review['capture_budget'];need(budget['finished'] and budget['remaining_payload_bytes']==0 and budget['resets']==26 and budget['target_dumps']==24 and budget['final_repeats']==1 and len(budget['events'])==52,'acknowledged complete captures')
 need(term['passed'] and term['children_exited'] and term['target_descriptors_empty'] and term['observed_target_contact']==[True,True] and term['first_error'] is None and term['original_error'] is None,'positive closed physical owners')
 need(review['full_result_sha256']==term['result']['full_result_sha256'] and review['plan_sha256']==term['plan_sha256'],'actual audit terminal joins')
 need(len(review['owners'])==2 and all(o['safe_to_exit'] and o['in_flight']==o['live_bytes']==o['exit_code']==0 for o in review['owners']),'safe native teardown')

def authority(batch):
 need(type(batch)is int and 0<=batch<54,'fixed batch0..53')
 need(BINDING_SHA is not None and sha(BINDING)==BINDING_SHA,'actual Engine-B closure/release binding pending')
 b=json.loads(BINDING.read_text());need(b['passed'] is True and b['released_paths']==list(NAMES),'explicit54-path release')
 expected={'review':REVIEW,'index':REVIEW.parent/'artifact-index.jsonl.gz','terminal':TERMINAL,'full_result':RAW/'resident-suite.json'}
 for key,path in expected.items():need(Path(b[key]['path'])==path and sha(path)==b[key]['sha256'],'fixed actual '+key+' identity')
 review=json.loads(REVIEW.read_text());term=json.loads(TERMINAL.read_text());closed(review,term)
 need(review['index_sha256']==b['index']['sha256'] and review['full_result_sha256']==b['full_result']['sha256'],'actual index/result binding')
 current=index(expected['index'],b['index']['sha256'])
 need(sha(CANON_REVIEW)==CANON_REVIEW_SHA and sha(CANON_COMPLETE)==CANON_COMPLETE_SHA,'immutable canonical authority')
 prior=json.loads(CANON_REVIEW.read_text());complete=json.loads(CANON_COMPLETE.read_text())
 need(prior['passed'] and prior['all12_exact'] and prior['physical_drain'] and complete['passed'] and complete['all_four_phases_passed'] and len(complete['batches'])==54,'completed canonical archives')
 old=index(CANON_REVIEW.parent/'artifact-index.jsonl.gz',prior['index_sha256']);archives={x['name']:x for x in complete['batches']};need(set(archives)==set(NAMES),'canonical54 member allowlist')
 rows={}
 for name in NAMES:
  actual=current[name];member=old[name];archive=archives[name];size=125561972 if '/rank0/' in '/'+name else 96181196
  need(actual['bytes']==member['bytes']==archive['source_bytes']==size and actual['sha256']==member['sha256'],'actual raw/canonical exact physical bytes')
  rows[name]=dict(relative_path=name,bytes=size,raw_sha256=actual['sha256'],canonical_archive=archive['usb'],canonical_archive_bytes=archive['archive_bytes'],canonical_archive_sha256=archive['archive_sha256'])
 need(sum(x['bytes'] for x in rows.values())==TOTAL,'fixed54 byte total')
 return rows[NAMES[batch]]
M.authority=authority
# Exact parent raw_held/descriptors/hash/member-readback/restore/fsync/separate
# release bodies remain unchanged; their globals bind only these fixed54 paths.
def main():
 ap=argparse.ArgumentParser(description=__doc__);g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--plan',action='store_true');g.add_argument('--verify',action='store_true');g.add_argument('--release-verified',action='store_true');ap.add_argument('--batch',type=int);a=ap.parse_args()
 if a.plan:
  rows=[authority(i) for i in range(54)];print(json.dumps(dict(source_only=True,rows=rows,recoverable_bytes=TOTAL),indent=2));return
 need(a.batch is not None,'explicit batch');print(json.dumps(M.verify(a.batch) if a.verify else M.release(a.batch),indent=2))
if __name__=='__main__':main()
