"""Read finished packet79 screens: exact outputs, acceptance and same-lane timing."""
import argparse,json,statistics
from screen_jobs import jobs,verify,winner,WRAPPER
from compare import load
from common import read,require,sha

def detail(job,lane):
 result=load(job,lane);root=WRAPPER/'evidence'/job['out'];summary=read(root/'run/summary.json');rows=summary['requests']
 guesses=sum(r['stats']['guesses'] for r in rows);hits=sum(r['stats']['hits'] for r in rows)
 draft=[d['draft_wall_ms'] for r in rows for d in r['draft_rows'] if d.get('hit') is not None]
 result.update(output=str(root),summary_sha256=sha(root/'run/summary.json'),draft_wall_ms=statistics.mean(draft) if draft else None,
   total_guesses=guesses,total_hits=hits,weighted_acceptance=hits/guesses if guesses else None,
   per_prompt={r['prompt_id']:dict(hits=r['stats']['hits'],guesses=r['stats']['guesses'],acceptance=r['acceptance'],
      guess_sequence=r['guess_sequence'],tokens_sha256=r['output_token_sha256']) for r in rows})
 return result

def main():
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--lane',choices=('A','B'),required=True);a=ap.parse_args();verify()
 selected=winner()['choice'] if a.lane=='B' else None;rows=[detail(j,a.lane) for j in jobs(a.lane,selected)]
 controls=[rows[0],rows[-1]];floor=max(r['rate'] for r in controls)
 for r in rows[1:-1]:
  r['gain_vs_faster_control_percent']=100*(r['rate']/floor-1)
  r['acceptance_change_vs_controls']=[r['weighted_acceptance']-c['weighted_acceptance'] for c in controls]
  r['proposal_sequences_equal_controls']=[all(r['per_prompt'][p]['guess_sequence']==c['per_prompt'][p]['guess_sequence'] for p in r['per_prompt']) for c in controls]
 print(json.dumps(dict(passed=all(r['exact'] for r in rows),lane=a.lane,rows=rows,device_measurements=True,
   evidence_label='screen',qualifying=False,metric='median across class medians, 99 intervals between emitted tokens 1 and100',
   realistic_final_gate=dict(passed=False,reason='128-token screens; full sealed record chain remains required')),indent=2))
if __name__=='__main__':main()
