"""Owned copy of the amended five-view rule; no sibling imports."""
import json,math
from decimal import Decimal
from pathlib import Path
P=Path(__file__).resolve().parent
METRIC="class_balanced_tok_s_1_100_intervals_after_ttft"
def require(ok,why):
    if not ok:raise ValueError(why)

def evaluate(rows,policy=None):
    policy=policy or json.loads((P/'readiness-policy.json').read_text())
    require([r['label'] for r in rows]==['A0','B0','A1','B1','A2'],'complete five-view bracket required')
    rates=[];signatures=[]
    for i,row in enumerate(rows):
        require(row['view']==('overlap' if i%2 else 'serial'),'maintenance order differs')
        requests=row['requests']
        require(row.get('passed') is True and len(requests)==12,'twelve exact prompts required')
        require(len({r['prompt_id'] for r in requests})==12,'duplicate prompt')
        require(all(r.get('passed') is True and r.get('exact_oracle') is True and r.get('cached_tokens')==0 and len(r['tokens'])==128 for r in requests),'128 exact uncached tokens per prompt required')
        signatures.append([(r['prompt_id'],r['prompt_token_sha256'],r['tokens']) for r in requests])
        value=row[METRIC]['median']
        require(type(value) in (float,int) and math.isfinite(value) and value>0,'invalid rate')
        rates.append(Decimal(str(value)))
    require(all(s==signatures[0] for s in signatures),'prompts or tokens differ across views')
    # The first view fills the immutable device expert cache in this one-load
    # bracket. Keep it exactness-gated and reported, outside speed comparison.
    controls=rates[2::2];candidates=rates[1::2]
    require(max(controls)<=min(controls)*(1+Decimal(str(policy['maximum_control_drift']))),'controls drift by more than 3%')
    require(all(c>=a*(1+Decimal(str(policy['minimum_gain_each_control']))) for c in candidates for a in controls),'both overlap views must beat EVERY serial control by at least 0.5%')
    return dict(passed=True,rates=list(map(float,rates)),control_drift=float(max(controls)/min(controls)-1),minimum_gain=float(min(candidates)/max(controls)-1),
                warmup_view=dict(label='A0',rate=float(rates[0]),exact=True,excluded_from_drift_and_comparison=True),
                comparison_controls=['A1','A2'],readiness_policy=policy['readiness_policy'])
