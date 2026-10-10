"""Reproducible planning arithmetic, NEVER measurements or UD header census."""
import importlib.util
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parent

def calculate():
    contract=json.loads((ROOT.parent/'packet1/tensor-contract.json').read_text())
    a=contract['active_bytes_per_decode']
    spec=importlib.util.spec_from_file_location('gguf_header_sizes',ROOT.parents[1]/'stage1/packet1b/loaders/headers.py')
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    # FORMAT.md/header table are the authority, not nominal bits/weight labels.
    types=m.TYPES
    target=a['tp4_target_weight_reads_with_hc_replication_floor_bytes']/4
    expert=a['target_routed_bytes']
    four={}
    for name,b in [('one_target_balanced',target),('M2_dense_once_disjoint_experts_balanced',target+expert/4),('M2_no_weight_reuse_balanced',2*target)]:
        ms=[b/r/1e6 for r in (537,507)]
        four[name]={'bytes_per_card':b,'floor_ms_537_to_507':ms,'33_69_ms_over_floor':[33.69/t for t in ms]}
    four['target_plus_proposal_balanced_bytes_per_card']=target+(a['mtp_proposal_weight_read_bytes']+3*a['mtp_hc_projection_replica_bytes_per_extra_rank'])/4
    nonexpert=133443446298-123327590400
    rows={}
    for name,typ in [('FP8',None),('UD-IQ4_XS idealized IQ4_XS',23),('UD-IQ3_XXS idealized IQ3_XXS',18),('UD-Q3_K_XL idealized Q3_K',11)]:
        if typ is None: b=4915800;block=None
        else:
            fmt,n,size=types[typ]; b=3*2560*640//n*size;block={'type':fmt,'elements':n,'bytes':size}
        active=b*10*48;bank=b*512*49
        rows[name]={'block':block,'expert_triplet_bytes':b,'target_expert_bytes':active,'mtp_expert_bytes':10*b,'expert_bank_49_layers_bytes':bank,'two_card_weight_floor_bytes':bank+nonexpert,'capacity_slack_before_KV_state_graphs':68484595712-(bank+nonexpert),'stream_ceiling_tps_aggregate19_38GBs':[r*1e9/active for r in (19,38)],'uniform_cache':{}}
        for c in (8,16,24):
            hit=min(c*1e9/bank,1);miss=active*(1-hit)
            rows[name]['uniform_cache'][str(c)]={'cache_GB_total_two_cards':c,'assumed_hit':hit,'miss_bytes_per_token':miss,'ceiling_tps_aggregate19_38GBs':[r*1e9/miss for r in (19,38)]}
    return {'status':'ARITHMETIC ONLY; idealized homogeneous expert grids; actual UD mixtures unknown','four_card':four,'two_card':rows}

if __name__=='__main__':print(json.dumps(calculate(),indent=2))
