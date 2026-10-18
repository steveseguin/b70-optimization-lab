"""Cross-run sensitivity only. The coordinator measures actual pipeline costs."""
import json
from analyze_probe import project,RECORD,HIT,MISS
H1=(14.23,14.69)
RESTORE=.980923
def bound(reserve):
 lo,hi=1.,3.
 for _ in range(64):
  ratio=(lo+hi)/2
  p=project(H1,[x*ratio for x in H1],RESTORE)
  rate=2000/(p['cases']['no_overlap_credit']['expected_two_token_ms']+reserve)
  if rate>=1.08*RECORD:lo=ratio
  else:hi=ratio
 return (lo+hi)/2
def model():
 return dict(diagnostic=True,measured=False,record_tok_s=RECORD,hit_ms=HIT,miss_ms=MISS,
  H1_ms=H1,restore_ms=RESTORE,bar_tok_s=1.08*RECORD,
  ideal_two_token_interval_max_ratio=bound(0),with_extra_2_38_ms_reserve_max_ratio=bound(2.38),
  sensitivity=[dict(ratio=r,**project(H1,[x*r for x in H1],RESTORE)) for r in (1.3,1.45,1.6)],
  limitations=['The steady pipeline runs a feedback draft pass plus two isolated recursive passes per tile.',
   'A miss in the second input discards the entire future tile and yields only one token before repair; the inherited ideal model assumes a completed two-token interval.',
   'Cloning, temporal copies, prefix selection, draft backup/restore, load imbalance and bubbles must be measured in the complete engine.',
   'The +8% ratio is an engineering sensitivity, never an adoption or performance verdict.'])
if __name__=='__main__':print(json.dumps(model(),indent=2))
