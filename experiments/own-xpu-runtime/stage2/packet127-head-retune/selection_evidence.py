"""Read-only historical timing evidence, current allocation census and model sensitivity."""
import gzip,hashlib,importlib.util,json,resource,statistics,time
from pathlib import Path
P=Path(__file__).resolve().parent;S=P.parent;ROOT=P.parents[3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
 sources={}
 def load(p):
  sources[str(p.relative_to(ROOT))]=sha(p);return json.loads(p.read_text())
 def module(name,p):
  sources[str(p.relative_to(ROOT))]=sha(p);spec=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
 old=load(S/'packet87t-transfer-micro/RESULT.json')
 report=module('p127_old_equations',S/'packet87t-transfer-micro/report.py')
 ns,model=report.equations(S/'packet87t-transfer-micro')
 for p in (S/'packet87-slack-model/model.py',S/'packet87-slack-model/DECISION.json',S/'packet85-critical-path/model.py'):sources[str(p.relative_to(ROOT))]=sha(p)
 legs=old['prediction']['scenarios']['idle/median']['target']['measured_E_I_V_ms'];ns['known']={k:0.0 for k in ns['known']}
 predictions=[dict(suffix_rows=n,old_model=ns['evaluate']('target',248320-n,tuple(legs))) for n in (46080,81920,122880)]
 slack=load(S/'packet123-partial-placement/slack.json')
 shape=load(P/'evidence/full-shape.json');census=[]
 for r in shape['runs']:
  n=r['view'].split('--')[-2];n=46080 if n=='split' else int(n)
  census.append(dict(suffix_rows=n,rank=r['rank'],arena_bytes=r['postload_device_bytes'],arena_headroom_bytes=r['arena_headroom_bytes'],weight_bytes=r['target_head_bytes']))
 rows=[]
 for dest in sorted((S/'screen/v4-lanes/evidence').glob('p120-B-grid-*')):
  if not (dest/'summary.json').exists():rows.append(dict(path=str(dest.relative_to(ROOT)),complete=False));continue
  window=load(dest/'window.json');summary=load(dest/'summary.json')
  complete=all(window.get(k) is True for k in ('passed','device_complete','lease_released'))
  assert window['files']['summary.json']==sha(dest/'summary.json')
  rows.append(dict(path=str(dest.relative_to(ROOT)),complete=complete,exact=summary['passed'],rate=summary['class_balanced_tok_s_1_100_intervals_after_ttft']['median'],request_count=summary['request_count'],tokens=summary['requested_max_new'],first99=__import__('bracket_report').paths(summary['requests'])))
 result=dict(schema='packet127.selection-evidence.v1',device_executed=False,historical_device_evidence=True,created_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),choices=[81920,122880],predictions=predictions,model_scope='Original packet87/87t lane, not bundle7. Predictions are not measurements. Larger suffixes test whether the balance moved with newer composition; no rank0 idle time is inferred.',packet118_slack_admission=slack['admission'],packet120=rows,packet120_complete=len(rows)==3 and all(r['complete'] for r in rows),census=census,sources=sources)
 result['packet120_relative_to_first_control_percent']=[100*(r['rate']/rows[0]['rate']-1) for r in rows[1:] if r['complete']] if rows and rows[0]['complete'] else []
 (P/'evidence/selection-evidence.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps({k:result[k] for k in ('packet120_complete','packet120_relative_to_first_control_percent','predictions')},indent=2))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(8*1024**3,8*1024**3));main()
