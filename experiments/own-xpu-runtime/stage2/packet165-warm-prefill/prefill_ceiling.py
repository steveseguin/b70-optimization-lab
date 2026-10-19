"""Conditional design arithmetic, NEVER a measured or promoted speed result."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
baseline=90.
rows=[]
for batch in (2,8):
    for fraction in (.5,.75,.9,1.):
        speed=baseline/((1-fraction)+fraction/batch)
        rows.append(dict(batch=batch,ideal_scalable_fraction=fraction,tok_s=speed,ttft_512_seconds=512/speed))
routes=[]
for batch in (2,8,32):
    union=512*(1-(1-10/512)**batch)
    routes.append(dict(batch=batch,expected_expert_union=union,weight_reuse_factor=10*batch/union))
value=dict(schema='packet165.design-sensitivity.v1',measured=False,promotion_eligible=False,
    provisional_baseline_tok_s=baseline,baseline_scope='brief estimate from roughly80-token two-card warm requests; NOT measured512 prefill',
    formula='S0 / ((1-f) + f/M)',assumptions=['f is unmeasured','zero added routing/dispatch/buffer/attention/pipeline overhead','all scalable work gets ideal1/M cost'],
    rows=rows,routing_model='hypothetical independent uniform ten-of512 expert selections; real overlap unmeasured',routes=routes,
    interpretation='conditional ceilings for the assumed model, not hardware limits, predictions, benchmarks or performance-curve points')
(P/'evidence/prefill-ceiling.json').write_text(json.dumps(value,indent=2)+'\n')
print('Design sensitivity computed; no measurement or performance claim.')
