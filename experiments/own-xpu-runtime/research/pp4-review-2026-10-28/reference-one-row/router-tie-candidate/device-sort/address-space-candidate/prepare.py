#!/usr/bin/env python3
"""Prepare explicit-local pointer experiment, leaving gated source untouched."""
import pathlib
import hashlib
import json
import difflib
import sys

here=pathlib.Path(__file__).resolve().parent
base=pathlib.Path(sys.argv[2]) if len(sys.argv)>2 else pathlib.Path('/dev/shm/sc117-reference-route-overlay-20261028-r4')
out=pathlib.Path(sys.argv[1]);out.mkdir()
source=json.loads((base/'source.json').read_text())
assert hashlib.sha256((base/'adapter.cpp').read_bytes()).hexdigest()=='282a0a90791464e8e001c54a29c8a0f73c637c62b86ae253f8c619bc520f6dc1'
changes={
 '#include "reference_sort_workspace.hpp"':'#include "reference_sort_addressed.hpp"',
 'int* order=reference_indices.get_multi_ptr<sycl::access::decorated::no>().get();':'auto order=reference_indices.get_multi_ptr<sycl::access::decorated::yes>().get();',
 'auto* stack=reference_frames.get_multi_ptr<sycl::access::decorated::no>().get();':'auto stack=reference_frames.get_multi_ptr<sycl::access::decorated::yes>().get();',
 'const float* probability=prob.get_multi_ptr<sycl::access::decorated::no>().get();':'auto probability=prob.get_multi_ptr<sycl::access::decorated::yes>().get();',
 'router_reference_sort::sort_indices_workspace(probability,order,N,stack)':'router_reference_sort_addressed::sort_indices_workspace(probability,order,N,stack)',
}
for name in ('adapter.cpp','route-capture-classes.inc'):
 original=(base/name).read_text();changed=original
 for old,new in changes.items():
  count=changed.count(old)
  if name=='adapter.cpp' or not old.startswith('#include'):assert count==1,(name,old,count)
  changed=changed.replace(old,new)
 (out/name).write_text(changed)
 if name=='adapter.cpp':(out/'address-space.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile='r4/adapter.cpp',tofile='addressed/adapter.cpp')))
(out/'reference_sort.hpp').write_bytes((base/'reference_sort.hpp').read_bytes())
(out/'reference_sort_addressed.hpp').write_bytes((here/'reference_sort_addressed.hpp').read_bytes())
test=(here.parent/'test_workspace.cpp').read_text().replace('#include "reference_sort_workspace.hpp"','#include "reference_sort_addressed.hpp"').replace('namespace rr=router_reference_sort;','namespace rr=router_reference_sort_addressed;')
(out/'test-addressed.cpp').write_text(test)
files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir()}
(out/'source.json').write_text(json.dumps(dict(schema='ownrt.reference-route-address-space-candidate.v1',base=str(base),base_source=source,files=files,gpu_executed=False,canonical_edited=False),indent=2)+'\n')
print(json.dumps(files))
