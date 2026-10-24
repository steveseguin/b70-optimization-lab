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
    s=replace(s,'namespace iq3::kopt {','namespace gsq_hc_one_sg {\nusing namespace iq3;\nusing iq3::kopt::Matrix;\nusing iq3::kopt::lane_dot;\ntemplate<Type T,unsigned SG> class HCKernel;')
    s=replace(s,'constexpr size_t rows_per_group=4;','constexpr size_t rows_per_group=1;')
    s=replace(s,'      h.parallel_for(p35_range0,','      h.parallel_for<HCKernel<T,SG>>(p35_range0,')
    s=replace(s,'(mul(count,span)+3)/4','(mul(count,span)+rows_per_group-1)/rows_per_group')
    s=replace(s,'// All four rows reach the sole workgroup barrier, including invalid/tail rows.','// Every row reaches the inherited workgroup barrier, including invalid/tail rows.')
    start=s.index('    switch(desc[0].type){'); end=s.index('\n  }\n};',start)
    s=s[:start]+'    return run<Type::BF16,32>(q,p,deps);'+s[end:]
    # Export only the original dense facade, with strict HC admission.
    s=replace(s,'std::string device_properties(){return properties;}\n','')
    start=s.index('ownrt::Event routed_gemv(');s=s[:start]+'}\n'
    anchor='  Multiply op;op.subgroup=sg;op.matrices=1;std::vector<ownrt::Allocation> ids;'
    s=replace(s,anchor,'  policy(t,rows,k,a,o,sg,fp32);\n'+anchor)
    s='#pragma once\n#include "policy.hpp"\n'+s
    return old,s
if __name__=='__main__':
    old,new=derive()
    (D/'one_sg.hpp').write_text(new)
    (D/'one_sg.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=str(P),tofile='one_sg.hpp')))
    sources=[P,B/'stage2/packet6-kopt/reference.hpp',B/'stage2/packet2/kernels/math.hpp',B/'stage2/packet2/kernels/grids.hpp',L/'integration/build/private/external/experiments/own-xpu-runtime/stage2/packet194-expert-diet-engine/kernel_guard.hpp',L/'graph/new-plan.json',L/'metadata/new-census.json',L/'dense-q6-p33/build/source/generic_engine.hpp']
    (D/'source-pins.json').write_text(json.dumps({str(p):sha(p) for p in sources},indent=2)+'\n')
    print(json.dumps({'source_only':True,'candidate_sha256':sha(D/'one_sg.hpp'),'original_sha256':EXPECTED}))
