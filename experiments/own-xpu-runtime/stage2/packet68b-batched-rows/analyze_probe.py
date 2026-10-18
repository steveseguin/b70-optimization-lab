"""Summarize paired real-fixture timings; project, never promote, depth two."""
import argparse,hashlib,json,math,statistics
from pathlib import Path
P=Path(__file__).resolve().parent
A1=.787;A2=.718;RECORD=51.033041;HIT=17.24;MISS=28.48
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def median(values):
 values=list(values)
 if not values or any(not math.isfinite(v) or v<=0 for v in values):raise ValueError('missing/nonpositive timing')
 return statistics.median(values)
def project(h1,h2,restore_ms=0):
 """Two-token pipeline block, NOT the blocking-verifier 1+a1+a1*a2 reward.

 Hit: one paired interval plus the calibrated serial draft/transfer overhead
 and a second recursive draft. First rejection discards both speculative
 rows: redo a pair. Second rejection redoes one row. Correction may retain
 the old 1.75 ms cancellation overlap credit; report both that case and zero
 credit. Copy/restore is charged once on either rejection. This cost model
 assumes two ready draft inputs and a correct causal M2 implementation;
 a duplicate-row cost screen does not establish either assumption.
 """
 overhead=max(0.,HIT-max(h1));extra_draft=2.38
 pair_hit=max(h2)+overhead+extra_draft
 p0=1-A1;p1=A1*(1-A2);p2=A1*A2
 corrected1=12.99;corrected2=corrected1*h2[0]/h1[0]
 cases={}
 for name,credit in [('no_overlap_credit',0.),('inherited_overlap_credit',corrected1-(MISS-HIT))]:
  costs={'both_hit':pair_hit,'first_miss':pair_hit+max(0.,corrected2-credit)+restore_ms,'second_miss':pair_hit+max(0.,corrected1-credit)+restore_ms}
  ms=p2*costs['both_hit']+p0*costs['first_miss']+p1*costs['second_miss'];rate=2000/ms
  cases[name]=dict(case_ms=costs,expected_two_token_ms=ms,projected_tok_s=rate,projected_gain_fraction=rate/RECORD-1,go_at_eight_percent=rate>=1.08*RECORD)
 baseline_ms=A1*HIT+(1-A1)*MISS
 # A depth-one redo that merely adds a second row still emits one confirmed
 # token. Do not manufacture a reward for an unverified/redundant row.
 redo_ms=baseline_ms+(1-A1)*(h2[0]-h1[0])
 return dict(probabilities=dict(first_miss=p0,second_miss=p1,both_hit=p2),reward_tokens=2,baseline_model_tok_s=1000/baseline_ms,reference_tok_s=RECORD,bar_tok_s=RECORD*1.08,overhead_ms=overhead,extra_draft_wall_ms=extra_draft,restore_ms=restore_ms,cases=cases,depth1_batched_redo=dict(projected_tok_s=1000/redo_ms,go_at_eight_percent=1000/redo_ms>=RECORD*1.08,assumption='one token per current pipeline cycle; second row earns nothing without a separately specified verified carry path'))
def analyze(root,restore_path=None):
 window=root/'window.json';w=json.loads(window.read_text())
 if w.get('passed') is not True or w.get('device_executed') is not True:raise ValueError('successful device window required')
 summary_path=root/'run/summary.json';summary=json.loads(summary_path.read_text())
 if summary.get('passed') is not True or summary.get('request_count')!=12 or summary.get('incident64',{}).get('tokens_compared')!=64 or not summary['incident64'].get('passed'):raise ValueError('all thirteen exact requests required')
 if summary.get('arithmetic')!='iq3-p49-split32-v1':raise ValueError('wrong target arithmetic')
 receipts=list((root/'run').glob('*/receipt.json'))
 requests=[json.loads(p.read_text()) for p in receipts]
 if len(requests)!=13 or not all(r.get('exact_oracle') is True for r in requests):raise ValueError('thirteen individual oracle receipts required')
 paths=sorted((root/'run').rglob('batched-rows.jsonl'))
 rows=[dict(json.loads(line),source=str(p)) for p in paths for line in p.read_text().splitlines() if line.strip()]
 if not rows or any(r.get('schema')!='packet68b.sample.v1' or r.get('byte_identity') is not True for r in rows):raise ValueError('missing/failed paired row bytes')
 ranks={};h1=[];h2=[]
 for rank in (0,1):
  rs=[r for r in rows if r['rank']==rank]
  if {r['fixture'] for r in rs}!={8,16,32} or len(rs)<39:raise ValueError('incomplete rank samples')
  groups={r['request_directory'] for r in rs}
  if len(groups)!=13 or any({r['fixture'] for r in rs if r['request_directory']==g}!={8,16,32} for g in groups):raise ValueError('missing request/rank sample coverage')
  dimensions={}
  for metric in ('wall_ms','device_span_ms','device_sum_ms'):
   a=median(r['H1'][metric] for r in rs);b=median(r['H2'][metric] for r in rs)
   dimensions[metric]=dict(H1=a,H2=b,ratio_of_medians=b/a,median_paired_ratio=median(r['H2'][metric]/r['H1'][metric] for r in rs))
  classes={}
  for name in sorted(set.intersection(*(set(r['H1']['classes_ms'])&set(r['H2']['classes_ms']) for r in rs))):
   av=[r['H1']['classes_ms'][name] for r in rs];bv=[r['H2']['classes_ms'][name] for r in rs]
   if min(av)<=0 or min(bv)<=0:continue
   a,b=median(av),median(bv);classes[name]=dict(H1_ms=a,H2_ms=b,ratio=b/a,shared_weight_kernel=all(name in r['batched_classes'] for r in rs))
  ranks[str(rank)]=dict(samples=len(rs),timings=dimensions,classes=classes)
  # Host span includes actual enqueue/wait cost, not just summed kernels.
  h1.append(dimensions['wall_ms']['H1']);h2.append(dimensions['wall_ms']['H2'])
 restore=0.;restore_status='not available: zero-cost sensitivity only';restore_identity=None
 if restore_path:
  r=json.loads(restore_path.read_text())
  if not r.get('passed') or not r.get('device_executed'):raise ValueError('restore receipt is not a successful device measurement')
  restore=float(r['medians']['restore_ms'])
  if not math.isfinite(restore) or restore<0:raise ValueError('invalid restore cost')
  restore_status='measured packet68 restore; different screen/configuration, conservative full charge';restore_identity=dict(path=str(restore_path),sha256=sha(restore_path))
 projection=project(h1,h2,restore)
 go=projection['cases']['no_overlap_credit']['go_at_eight_percent']
 return dict(schema='packet68b.analysis.v1',passed=True,diagnostic=True,device_executed=True,measured_half_costs=ranks,projection=projection,decision='GO to a causal prototype cost screen' if go and restore_path else 'NO-GO for adoption; '+('restore cost missing' if go else 'below +8% conservative projected bar'),provisional_zero_restore_bar_pass=go,restore_status=restore_status,restore_identity=restore_identity,limitations=['Duplicate rows share the same routes; expert-union timings on differing routes require a subsequent causal fixture.','GDN/conv/QSA cores are independent serial rows from the same initial state; consecutive-position dependency is not qualified.','Prepared replay wall time excludes the separately logged initial copies, capture preparation, input lookup, and publication. The calibrated overhead is a cross-run estimate.','Current hit/miss numbers and acceptance rates are from different screens; projection is not a speed result.','All thirteen packet49 streams and private row bytes must pass; a screen does not replace fresh-server speed or promotion gates.'],inputs={str(p):sha(p) for p in [window,summary_path,*receipts,*paths]},samples=rows)
def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('window',type=Path);ap.add_argument('--restore-summary',type=Path);ap.add_argument('--output',type=Path);a=ap.parse_args();result=analyze(a.window,a.restore_summary);text=json.dumps(result,indent=2)+'\n'
 if a.output:a.output.write_text(text)
 else:print(text,end='')
if __name__=='__main__':main()
