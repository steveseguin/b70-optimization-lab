#!/usr/bin/env python3
"""Source-only deterministic derivation; never builds, loads payloads or invokes a device."""
import difflib, hashlib, json
from pathlib import Path
D=Path(__file__).resolve().parent
L=D.parent
B=L/'integration/build/private/source/diet-native/native-base/experiments/own-xpu-runtime'
P=B/'stage2/packet6-kopt/kernels.cpp'
EXPECTED='08f249a46ae60aed5b5fdb139a5a38b5d4a512c5090e35d93200fa007829fc5e'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def replace(s,a,b):
    assert s.count(a)==1, a[:100]
    return s.replace(a,b)
def derive():
    assert sha(P)==EXPECTED
    old=P.read_text(); s=old
    s=replace(s,'namespace iq3::kopt {','namespace gsq_iq4_direct {\nusing namespace iq3;\nusing iq3::kopt::Matrix;\nusing iq3::kopt::lane_dot;\ntemplate<Type T,unsigned SG> class DirectKernel;')
    s=replace(s,'      sycl::local_accessor<uint8_t,1> storage(stride*rows_per_group,h);\n','')
    s=replace(s,'      h.parallel_for(p35_range0,','      h.parallel_for<DirectKernel<T,SG>>(p35_range0,')
    s=replace(s,'          auto local=storage.template get_multi_ptr<sycl::access::decorated::no>().get()+row_in_group*stride;\n','')
    s=replace(s,'            if(layout(T).elements!=1)stage_row<SG>(source,local,d.rb,lane);\n','')
    s=replace(s,'          // All four rows reach the sole workgroup barrier, including invalid/tail rows.\n          it.barrier(sycl::access::fence_space::local_space);\n','          // Direct global reads; no shared local storage or workgroup barrier.\n')
    s=replace(s,'dot<T,SG>(layout(T).elements==1?source:local,x,d.activation,d.k,lane)','dot<T,SG>(source,x,d.activation,d.k,lane)')
    start=s.index('    switch(desc[0].type){'); end=s.index('\n  }\n};',start)
    s=s[:start]+'    return run<Type::IQ4_NL,32>(q,p,deps);'+s[end:]
    # Expose only the narrow routed facade; retain inherited binding machinery.
    start=s.index('std::string device_properties(){'); end=s.index('ownrt::Event routed_gemv(',start)
    s=s[:start]+s[end:]
    start=s.index('ownrt::Event fused_gemv(')
    s=s[:start]+'}\n'
    anchor='  if(!r || !status)throw std::invalid_argument("kopt routing handles required");'
    s=replace(s,anchor,'  policy(t,experts,rows,k,count,span,a,o,sg,fp32);\n'+anchor)
    s='#pragma once\n#include "policy.hpp"\n'+s
    return old,s
if __name__=='__main__':
    old,new=derive()
    (D/'direct.hpp').write_text(new)
    (D/'direct.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(P),tofile='direct.hpp')))
    sources=[P,B/'stage2/packet6-kopt/reference.hpp',B/'stage2/packet2/kernels/math.hpp',B/'stage2/packet2/kernels/grids.hpp',L/'integration/build/private/external/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/kernel_guard.hpp',L/'graph/new-plan.json',L/'metadata/new-census.json',L/'expert-iq3xxs-block/engine/build/source/generic_engine.hpp']
    (D/'source-pins.json').write_text(json.dumps({str(p):sha(p) for p in sources},indent=2)+'\n')
    print(json.dumps({'source_only':True,'direct_sha256':sha(D/'direct.hpp'),'original_sha256':EXPECTED}))
