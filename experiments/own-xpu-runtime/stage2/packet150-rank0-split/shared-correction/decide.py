"""Read completed packet149 v5 and apply the owner's approximately 1 ms gate.

CPU only. No packet149 writes, model payload reads, queueing or native launches.
Snapshots use .json.txt so their historical embedded paths remain provenance,
not active build/admission dependencies of packet150.
"""
import datetime,hashlib,json,resource,statistics,sys
from pathlib import Path
P=Path(__file__).resolve().parent
SOURCE=P.parents[1]/'packet149-shared-correction-probe/v5'

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def main():
 output=SOURCE/'evidence/device-xchg-v5-B'
 names=('bracket-summary.json','window.json','identity.json','run/teardown.json')
 before={n:sha(output/n) for n in names}
 # This validates full window hashes, exact oracle tokens, acceptance and draft
 # proposal identity, reset/isolation, native teardown and the original seal.
 sys.path.insert(0,str(SOURCE))
 from p149_v5_compare import load
 report=load(output)
 assert report['passed'] and report['draft_proposals_identical']
 rows=report['scheduling_costs']['views'];assert len(rows)==5
 controls=[v['corrected_half']['mean_ms'] for v in rows if v['choice']=='control']
 candidates=[v for v in rows if v['choice']=='candidate']
 assert len(controls)==3 and len(candidates)==2
 assert all(v['status']=='measured' and v['miss_count']==331 for v in rows)
 for v in rows:
  audit=v['exchange_audit'];assert audit['covered_misses']==v['miss_count']
  assert audit['counts']==([0] if v['choice']=='control' else [96])
 baseline=statistics.mean(controls)
 costs=[v['corrected_half']['mean_ms']-baseline for v in candidates]
 for value,v in zip(costs,candidates):assert abs(value-v['exchange_cost_per_miss_ms'])<1e-10
 assert min(costs)>1.0,'The high-cost closeout does not apply; prototype branch must be reviewed.'
 assert before=={n:sha(output/n) for n in names},'packet149 evidence changed during validation'
 snapshots=[]
 for n in names:
  target=P/'evidence'/(n.replace('/','-')+'.txt');target.write_bytes((output/n).read_bytes())
  assert sha(target)==before[n]
  snapshots.append(dict(path=str(target.relative_to(P)),sha256=sha(target),original_location=str(output/n)))
 result=dict(schema='packet150.shared-correction-decision.v1',decision='do not build shared-correction prototype',
  owner_exchange_gate_ms_per_miss=1.0,exchange_gate_passed=False,prototype_built=False,device_executed_by_this_task=False,
  measured_packet149_evidence=True,validated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
  source_reporter_path=str(SOURCE/'p149_v5_compare.py'),source_reporter_observed_digest=sha(SOURCE/'p149_v5_compare.py'),
  arithmetic='iq3-p49-split32-v1',lane='B',model_lifetimes=1,prompts_per_view=12,output_tokens_per_prompt=128,
  control_corrected_half_mean_ms=controls,mean_of_control_means_ms=baseline,
  probe_corrected_half_mean_ms=[v['corrected_half']['mean_ms'] for v in candidates],
  exchange_cost_ms_per_miss=costs,mean_exchange_cost_ms_per_miss=statistics.mean(costs),
  control_half_range_ms=max(controls)-min(controls),control_rate_drift_percent=report['control_drift_percent'],
  misses_per_view=331,exchanges_per_probe_miss=96,
  derivation='E_i = probe-view mean corrected-half time - mean of three control-view means; '
             'net saving = G - E - A, so a 2..3 ms net saving needs G >= E + A + 2..3 ms.',
  required_gross_saving_for_net_2_to_3_ms_ignoring_additional_cost=[statistics.mean(costs)+2,statistics.mean(costs)+3],
  caveat='Measured serialized 96-exchange surrogate across large attention and routed-expert projections. '
         'Not a measurement of an expert-only or coalesced schedule; no subset cost extrapolated. '
         'Unchanged target computation still ran in full. No shared compute speed or quality result.',
  snapshots=snapshots,split_readiness_unchanged=True)
 (P/'decision.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('decision','mean_of_control_means_ms','exchange_cost_ms_per_miss','mean_exchange_cost_ms_per_miss')}))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
