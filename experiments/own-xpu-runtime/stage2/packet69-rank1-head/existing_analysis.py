"""CPU-only reread of packet64 measurements, no model payload reads."""
from pathlib import Path
import json
from summarize import base_summarize
from outside import byte_counts,roofline
P=Path(__file__).resolve().parent
run=P.parent/'screen/v3-attr/evidence/packet64-attribution-B-a/run'
r=base_summarize(run);b=byte_counts()
d=next(x for x in r['draft_breakdown'] if x['category']=='head_prefix')
out=dict(passed=True,device_executed=False,source_run=str(run),sources=r['sources'],rank_halves=r['rank_halves'],outside_layers=r['outside_layers'],draft_breakdown=r['draft_breakdown'],tensor_identity=b,
 draft_head_roofline_measured=roofline(b['draft_prefix_resident_bytes'],d['measured']['mean_us']),
 draft_head_roofline_scaled_estimate=roofline(b['draft_prefix_resident_bytes'],d['estimated_scaled_mean_us']),
 target_head_time=None,final_norm_time=None,argmax_time=None,
 missing='packet64 recorder excludes target logits/argmax/final.*; no decomposition can be recovered honestly')
(P/'evidence/existing-analysis.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:out[k] for k in ('draft_head_roofline_measured','draft_head_roofline_scaled_estimate','missing')},indent=2))
