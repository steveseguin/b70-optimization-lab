#!/usr/bin/env python3
"""Read retained source/receipt evidence; no model/device access."""
import hashlib
import json
from pathlib import Path
import statistics
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p46=HERE.parent/'packet46-specialized';p48=HERE.parent/'packet48-gemv'
    evidence=[p46/f'evidence/p46-a-t{i}/run/iterations.jsonl' for i in (1,2)]
    evidence += [p48/f'evidence/p48-d-t{i}/summary.json' for i in (1,2)]
    controls={}
    for old,new in [('expsgate','expsgate.iq2'),('expsdown','expsdown'),('gdn.qkv','gdn.qkv.q6'),('gdn.z','gdn.z.q6')]:
        pairs=[]
        for i in range(2):
            rows=[json.loads(x) for x in evidence[i].read_text().splitlines()]
            full=statistics.median(r['classes_ns'][old]/1000 for r in rows if r['layer']==4 and r['mode']=='current' and not r['warmup'])
            isolated=json.loads(evidence[i+2].read_text())['classes'][new]['1']['all']
            pairs.append(dict(p46_full_layer_current_us=full,p48_isolated_current_us=isolated['old_us'],
                              p48_isolated_candidate_us=isolated['new_us'],ratio=isolated['old_us']/full))
        controls[new]=pairs
    files=evidence+[p46/'layer_bench.cpp',p46/'fixture_bytes.hpp',p46/'dispatch-baseline.json',p48/'bench.cpp',
                    p48/'PREREGISTRATION.md',HERE.parent/'packet45-merged3/p33_submit.cpp',HERE.parent/'packet45-merged3/p39_sycl.hpp',
                    HERE.parent/'packet34-replay-bench/directory.tsv']
    result=dict(schema='ownrt.packet48b.reconciliation.v1',device_executed=False,model_payload_read=False,
                production_geometry_matches=True,ordinary_experts='IQ2_S gate/up, IQ4_NL down',ordinary_dense='Q6_K K=2560, rows=10240/6144, split=1',
                direct_production_kernel_controls=['expsgate.iq2','expsdown'],
                adapted_control_wrappers=['gdn.qkv.q6','gdn.z.q6','expsgate.iq3','gdn.qkv.q8','gdn.z.q8'],
                known_confounders=['full-layer versus isolated scheduling/cache context','32 repeated synthetic blocks per tensor versus independently changing row bytes','10 warmup/200 pairs versus 4 warmup/24 pairs','actual p33 generic production submission versus compile-time non-routed dense wrapper'],
                single_cause_proven=False,controls=controls,
                integration_eligible=[],pending='two fresh matched full-layer exactness and timing windows; no p48 speed claim admitted',
                source_and_evidence_sha256={str(p.relative_to(ROOT)):sha(p) for p in files})
    (HERE/'reconciliation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(dict(production_geometry_matches=True,integration_eligible=[],device_executed=False)))
if __name__=='__main__':main()
