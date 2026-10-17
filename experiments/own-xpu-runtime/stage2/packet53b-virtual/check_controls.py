#!/usr/bin/env python3
"""Read-only match of screen control bodies and packet49c integration inputs."""
import json,re
from pathlib import Path
from preparation import exclusive_cpu_work
from window_support import HERE,REPO,sha,save,require

def main():
    with exclusive_cpu_work():
        root=HERE.parent
        a=(root/'packet51-round2/candidate.hpp').read_text().split('template<Type T,unsigned K>inline float dense_lane',1)[1].rsplit('} // namespace',1)[0]
        b=(root/'packet49c-round2/p49c_kernel.hpp').read_text().split('template<Type T,unsigned K>inline float dense_lane',1)[1].rsplit('} // namespace',1)[0]
        a=a.replace('p48::load32','load32').replace('constexpr unsigned wg=256;','')
        a=re.sub(r'\bwg\b','256',a)
        require(a==b,'HC control body changed beyond local load helper and literal launch constant')
        old=(root/'packet48b-production/candidate.hpp').read_text().split('template<Type T,unsigned K>struct Kernel',1)[1]
        integrated=(root/'packet49c-round2/p49b_expert_kernel.hpp').read_text().split('template<Type T,unsigned K>struct Kernel',1)[1]
        integrated=integrated.replace('p49bgemv::','p48::').replace('p[16]','p[8]').replace('p[17]','p[9]')
        require(old==integrated,'expert control kernel differs beyond namespace and control binding offsets')
        layout=(root/'packet49c-round2/p49b_gemv.hpp').read_text().replace('namespace p49bgemv','namespace p48').replace('#include "p33_candidates.hpp"','#include "../packet45-merged3/p33_candidates.hpp"').replace('#include "p42_expert.hpp"','#include "../packet45-merged3/p42_expert.hpp"')
        require(layout==(HERE/'production_gemv.hpp').read_text(),'compact production pitch/decode differs')
        files=['packet53b-virtual/production_gemv.hpp','packet51-round2/candidate.hpp','packet51-round2/dispatch-baseline.json',
               'packet48b-production/candidate.hpp','packet48-gemv/gemv.hpp']
        for name in ('main.cpp','p49c_kernel.hpp','p49c_submit.cpp','p49b_expert_kernel.hpp','p49b_expert_submit.cpp','p49b_gemv.hpp','prepared_submission.hpp','p30_small.cpp','p30_small.hpp','p30_submit.cpp','small_gemv.cpp','dispatch-speed6.json'):
            path=root/'packet49c-round2'/name
            if path.exists():files.append('packet49c-round2/'+name)
        # Small control already calls the original engine dispatch. Require the
        # selected rows4 code and original p49c copy to be byte-identical.
        for name in ('p30_small.cpp','p30_small.hpp','p30_submit.cpp','small_gemv.cpp'):
            require((root/'packet45-merged3'/name).read_bytes()==(root/'packet49c-round2'/name).read_bytes(),'small control differs: '+name)
            files.append('packet45-merged3/'+name)
        screen=json.loads((root/'packet51-round2/dispatch-baseline.json').read_text())
        production=json.loads((root/'packet49c-round2/dispatch-speed6.json').read_text())
        require(screen==production,'screen dispatch differs from 49c')
        require(screen['fusions']['small.ffn']=='p30.small.rows4','small tuple selected control differs')
        save(HERE/'control-identity.json',dict(passed=True,device_executed=False,
            hc='identical dense body after local load32 qualification and literal256 normalization',
            small='byte-identical p30 source and dispatch-speed6; actual engine grouped call, one event',
            experts='identical packet49c compact pitch/decode; identical packet48b/p49b body after namespace and control binding offset normalization',
            sources={str((root/f).relative_to(REPO)):sha(root/f) for f in files}))
        print('production control source checks passed')
if __name__=='__main__':main()
