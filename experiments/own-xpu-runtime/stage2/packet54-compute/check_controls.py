#!/usr/bin/env python3
"""Read-only proof that the screen's inherited controls are packet49c bodies."""
import json
from preparation import exclusive_cpu_work
from window_support import HERE,REPO,require,save,sha

def main():
    with exclusive_cpu_work():
        root=HERE.parent; old=root/'packet45-merged3'; prod=root/'packet49c-round2';files=[]
        for n in ('round2.hpp','round2_submit.cpp','specialised.hpp','specialised_submit.cpp','kernels.hpp','p33_submit.cpp','p33_candidates.hpp','p28/submit.cpp','p28/dense.hpp','route42.hpp'):
            require((old/n).read_bytes()==(prod/n).read_bytes(),'production control differs: '+n)
            files.extend([old/n,prod/n])
        for n,removed in [('runtime_kernels.hpp',['  c.qsa_split32=spec.implementation==12;\n']),('adapter.cpp',['#include "p49_qsa_submit.hpp"\n',' if(s.implementation==12&&shape.op==ng::attention_score)return p49::attention(d,shape,a,bindings[s.ni+s.no+s.nw],deps);\n'])]:
            text=(prod/n).read_text()
            for line in removed:
                require(text.count(line)==1,'known QSA-only delta changed');text=text.replace(line,'')
            require(text==(old/n).read_text(),'non-QSA control adapter changed')
            files.extend([old/n,prod/n])
        screen=root/'packet51-round2/candidate.hpp';a=screen.read_text();b=(prod/'p49c_kernel.hpp').read_text()
        a=a[a.index('inline void route_exp_host'):a.index('template<Type T,unsigned K>inline float dense_lane')]
        b=b[b.index('inline void route_exp_host'):b.index('template<Type T,unsigned K>inline float dense_lane')]
        require(a.replace('p51','p49c')==b,'selected route control differs')
        dispatch=root/'packet51-round2/dispatch-baseline.json'
        require(json.loads(dispatch.read_text())==json.loads((prod/'dispatch-speed6.json').read_text()),'production dispatch differs')
        files.extend([screen,prod/'p49c_kernel.hpp',dispatch,prod/'dispatch-speed6.json',prod/'main.cpp',prod/'p49c_submit.cpp',HERE/'bench.cpp'])
        bank=root/'packet53b-virtual/evidence-copy/p53b-a-summary.json';r=json.loads(bank.read_text())
        require(r['passed'] and r['owner_saved_us']==[23.4385,23.4375] and not r['virtualization_proceeds'],'banked evidence differs');files.append(bank)
        save(HERE/'control-identity.json',dict(passed=True,device_executed=False,route='identical selected route after namespace substitution',other_controls='byte-identical sources; only unrelated split32 QSA hooks removed from adapter comparison',banked_owner_us=r['owner_saved_us'],sources={str(p.relative_to(REPO)):sha(p) for p in files}))
        print('packet49c production control bodies and banked receipt match')
if __name__=='__main__':main()
