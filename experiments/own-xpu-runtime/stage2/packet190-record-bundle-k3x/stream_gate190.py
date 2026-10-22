"""Completed-request stream presence/format/exactness, no wall-clock limits."""
import math

def check(result):
 if not result.get('passed') or not result.get('oracle_check',{}).get('passed'):
  raise ValueError('completed request must pass the unchanged exact oracle')
 tokens=result['tokens'];stamps=result['token_timestamps']
 if not tokens or len(tokens)!=len(stamps) or not all(type(t) in (int,float) and math.isfinite(t) for t in stamps) or not all(b>a for a,b in zip(stamps,stamps[1:])):
  raise ValueError('missing or malformed token completion stream')
 trace=result['rank_trace']
 if not trace or {r['rank'] for r in trace}!={0,1}:
  raise ValueError('missing rank completion stream')
 if any(not isinstance(r,dict) or type(r.get('op')) is not int for r in trace):
  raise ValueError('malformed rank completion stream')
 if result.get('cached_tokens')!=0 or result.get('arithmetic')!='iq3-p49-split32-v1':
  raise ValueError('request cache/arithmetic identity differs')
 return dict(passed=True,token_events=len(stamps),rank_events=len(trace),exact=True,wall_clock_limit=False)
