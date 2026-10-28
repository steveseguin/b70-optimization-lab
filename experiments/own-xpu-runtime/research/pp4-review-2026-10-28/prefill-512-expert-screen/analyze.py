#!/usr/bin/env python3
"""Read root-owned case logs; no launch, retry, build or device operations."""
import hashlib,json,pathlib,re,statistics,sys
here=pathlib.Path(__file__).resolve().parent
registration=json.loads((here/'registration.json').read_text());logs=pathlib.Path(sys.argv[1]);cases=[]
for c in registration['cases']:
 p=logs/(c['id']+'.log')
 if not p.exists():p=logs/c['id']/'stdout.log'
 text=p.read_text()
 assert 'TOTAL FAILS 0' in text and 'DIFFERS' not in text and 'REFUSED' not in text,c['id']
 gates=[l for l in text.splitlines()if l.startswith('GATE '+c['id']+' ')]
 assert len(gates)==8 and all(l.endswith(' PASS')for l in gates),(c['id'],gates)
 samples={}
 for label,k,cold,hot in re.findall(r'^SAMPLE (\S+) ordinal=(\d+) cold_us=([\d.]+) warm_us=([\d.]+)$',text,re.M):
  samples.setdefault(label,[]).append((int(k),float(cold),float(hot)))
 assert set(samples)=={'paired256_bucket_plus_tile_span','whole512_bucket_plus_tile_span'}
 assert all(len(v)==12 and sorted(x[0]for x in v)==list(range(12))for v in samples.values())
 ratios={}
 for mode,col in [('cold',1),('hot',2)]:
  med={label:statistics.median(x[col]for x in v)for label,v in samples.items()}
  ratios[mode]=med['whole512_bucket_plus_tile_span']/med['paired256_bucket_plus_tile_span']
 cases.append({'id':c['id'],'family':c['family'],'ratios':ratios,'samples':samples,'log':str(p),'log_sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
weighted={}
for mode in ['cold','hot']:
 total=0;weight_sum=0
 for family in {c['family']for c in cases}:
  ratio=statistics.median(c['ratios'][mode]for c in cases if c['family']==family)
  weight=next(c['profile_weight_percent']for c in registration['cases']if c['family']==family)
  total+=weight*(1-ratio);weight_sum+=weight
 weighted[mode]=100*total/weight_sum
out={'schema':'ownrt.prefill512-operator-screen.v1','cases':cases,'weighted_routed_family_reduction_percent':weighted,'supports_integration_review':all(v>10 for v in weighted.values()),'limits':'Historical actual routes from synthetic rank1 inputs, fixed synthetic activations and actual admitted weights. Operator hot/cold event spans include bucket+tile, not an endpoint prediction or engine/state qualification. Device/lifecycle postflight is separate root authority.'}
print(json.dumps(out,indent=2,ensure_ascii=False))
