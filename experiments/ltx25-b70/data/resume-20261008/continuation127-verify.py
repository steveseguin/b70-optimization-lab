#!/home/steve/.venvs/ltx25-baseline/bin/python -B
"""CPU-only source closure, recursive manifest and test discovery record."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[4]
LANE=ROOT/'experiments/ltx25-b70'
SRC=LANE/'recovery/20261010-continuation127-stream'
OUT=LANE/'data/resume-20261008/continuation127-tests'
sys.path.insert(0,str(SRC))
import runtime_packet as rp
import plan
import session

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(name,value):
    (OUT/name).write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')

seal=json.loads((OUT/'seal.json').read_text())
manifest=rp.verify_packet(rp.PACKET,seal['manifest_sha256'])
envelope=json.loads((rp.PACKET/'resolution/stream-plan.json').read_text())
assert envelope==plan.build_plan()
assert envelope['plan_sha256']==rp.PLAN_SHA==session.PLAN_SHA256
assert rp.PARENT_SHA=='fe5ce9e09b7e8c86ac659c20430f85b3c83cb35bf5e8476f740610da82b60aa4'
for path,digest in manifest['files'].items():
    assert sha(rp.PACKET/path)==digest,path
caches=[str(p) for root in (SRC,rp.PACKET,OUT) for p in root.rglob('*')
        if p.name=='__pycache__' or p.suffix=='.pyc']
assert not caches,caches
save('recursive-verification.json',{
    'status':'passed','packet':str(rp.PACKET),'manifest_sha256':seal['manifest_sha256'],
    'inner_plan_sha256':envelope['plan_sha256'],
    'plan_file_sha256':sha(rp.PACKET/'resolution/stream-plan.json'),
    'parent_manifest_sha256':rp.PARENT_SHA,'files':len(manifest['files']),
    'recursive_parent_verification':True,'pycache_count':0,'pyc_count':0,
    'preview_source_unchanged_from126':sha(SRC/'stream_preview.py')==sha(rp.PARENT/'resolution/components/stream_preview.py'),
    'maintenance_source_unchanged_from126':sha(rp.PACKET/'source/main.py')==sha(rp.PARENT/'source/main.py')})
files=list(SRC.glob('*.py'))
for path in files:
    ast.parse(path.read_text(),filename=str(path))
suite=unittest.defaultTestLoader.discover(str(SRC),pattern='test_*.py')
def ids(node):
    if isinstance(node,unittest.TestSuite):
        return [item for child in node for item in ids(child)]
    return [node.id()]
all_ids=ids(suite)
assert len(all_ids)==len(set(all_ids))
assert not any('_FailedTest' in i for i in all_ids)
save('recovery-final-discovery.json',{'count':len(all_ids),'test_ids':all_ids})
save('static-validation.json',{'status':'passed','python_ast_files':len(files),
    'inner_plan_pins_match':True,'generated_plan_matches_seal':True,
    'parent126_pinned':True,'full_test_discovery_count':len(all_ids),
    'namespace_and_numerical_identity':'Covered by6 parent numerical/graph tests in full recovery suite.'})
print(json.dumps({'files':len(manifest['files']),'test_discovery':len(all_ids),
                  'manifest_sha256':seal['manifest_sha256'],'inner_plan_sha256':envelope['plan_sha256']}))
