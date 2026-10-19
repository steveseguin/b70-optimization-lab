"""Recompute the packet153 screen from retained tokens, clocks and proposals."""
import hashlib,json,math,statistics
from pathlib import Path
O=Path(__file__).resolve().parent;ROOT=O.parents[3];STAGE=ROOT/'experiments/own-xpu-runtime/stage2'
SUMMARY=STAGE/'packet153-snapshot-host/v5/evidence/device-static-v5-B-p153b/bracket-summary.json'
ORACLE=STAGE/'packet49-integrate/oracle/results'
CLASSES={'incident-retrospective':'operations','code-review':'code','customer-email':'prose','sql-debugging':'code','release-plan':'operations','benchmark-analysis':'analysis','architecture-tradeoff':'analysis','bug-report-synthesis':'operations','technical-guide':'documentation','risk-register':'structured-writing','performance-hypotheses':'analysis','decision-memo':'prose'}
def need(v,m):
 if not v:raise ValueError(m)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def evaluate(rates,lanes_idle=True):
 need(len(rates)==5 and all(type(x) in (int,float) and math.isfinite(x) and x>0 for x in rates),'five finite positive rates required')
 controls=[rates[i] for i in (0,2,4)];candidates=[rates[i] for i in (1,3)]
 gain=100*(min(candidates)/max(controls)-1);drift=100*(max(controls)/min(controls)-1)
 need(gain>=.2,'static must beat EVERY warm control by >=0.2%')
 need(drift<=1,'control drift exceeds 1%')
 need(lanes_idle or min(candidates)>58.798109*1.02,'+2% record-chain rule requires coordinator idle-lane exception')
 return dict(passed=True,rates=rates,control_indices=[0,2,4],warm_control_indices=[0,2,4],candidate_indices=[1,3],minimum_gain_percent=gain,control_drift_percent=drift,threshold_percent=.2,idle_lanes_exception=lanes_idle,record_gain_measured=False,scope='screen admission only; fresh chain WS128 must exceed 58.798109')
def verify(path=SUMMARY):
 path=Path(path);root=path.parent;summary=json.loads(path.read_text());views=summary['views'];pins={str(path.relative_to(ROOT)):sha(path)}
 def read(f):pins[str(f.relative_to(ROOT))]=sha(f);return json.loads(f.read_text())
 need(summary['passed'] is True and summary['all_13_exact'] is True and summary['model_lifetimes']==1,'complete one-load exact bracket required')
 need(len(views)==5 and [x['choice'] for x in views]==['control','candidate','control','candidate','control'],'C/X/C/X/C required')
 identity=read(root/'identity.json');binding=read(O/'inputs/packet153-native.json')
 need(read(root/'window.json')['passed'] is True and read(root/'run/device-isolation.json')['passed'] is True,'bracket completion/isolation failed')
 active=read(STAGE/'packet155-record-bundle9/selection.json')
 need(identity['binary_sha256']==binding['binaries']['build/device/own-rt-iq3']['sha256'],'bracket binary identity differs')
 rates=[];all_counts=[];all_proposals=[]
 for i,view in enumerate(views):
  need(view['index']==i and view['all_13_exact'] is True and view['exact_count']==13,'view exactness failed')
  dest=root/'run/views'/f'{i:02d}-{view["choice"]}';need(Path(view['output'])==dest,'view path differs')
  selection=identity['bracket']['views'][i];expected=json.loads(json.dumps(active));expected['choices']['snapshot_host']='production' if view['choice']=='control' else 'static'
  selection_path=Path(selection['selection']);need(read(selection_path)==expected and sha(selection_path)==selection['selection_sha256'] and selection['max_new']==128,'bracket selection differs from bundle8/static-only delta')
  row=read(dest/'summary.json');need(row['arithmetic']=='iq3-p49-split32-v1' and row['kv_dtype']=='BF16' and row['cached_tokens']==0,'arithmetic/cache differs')
  need(row['requested_max_new']==128 and row['request_count']==12 and row['passed'] is True,'complete 128-token suite required')
  requests=row['requests'];need([r['prompt_id'] for r in requests]==list(CLASSES),'fixed complete suite required')
  grouped={};counts=[];proposals={}
  for r in [read(dest/'incident64/receipt.json'),*requests]:
   incident=r is not None and len(r['tokens'])==64
   prompt=r['prompt_id'];cap=64 if incident else 128
   oracle=read(ORACLE/prompt/'result.json')['tokens']
   need(r['tokens']==oracle[:cap] and len(r['tokens'])==cap and r['passed'] is True and r['exact_oracle'] is True and r['cached_tokens']==0,'oracle tokens differ')
   name='incident64' if incident else prompt
   trace=dest/name/'rank1/draft-rows.jsonl';pins[str(trace.relative_to(ROOT))]=sha(trace)
   values=[[x[k] for k in ('draft_position','confirmed_token','guess','head')] for x in (json.loads(line) for line in trace.read_text().splitlines() if line.strip())]
   need(values and any(x[3] for x in values),'proposal stream empty')
   proposals[name]=dict(rows=len(values),sha256=hashlib.sha256(json.dumps(values,separators=(',',':')).encode()).hexdigest())
   if incident:continue
   ts=r['token_timestamps'];need(len(ts)==128 and all(math.isfinite(t) for t in ts) and all(b>a for a,b in zip(ts,ts[1:])),'timestamp format')
   need(r['prompt_class']==CLASSES[prompt] and r.get('repeat',1)==1,'prompt class/repeat differs')
   grouped.setdefault(r['prompt_class'],[]).append(99/(ts[99]-ts[0]))
   counts.append(dict(prompt_id=prompt,hits=r['hits'],guesses=r['guesses']))
  rate=statistics.median(statistics.median(v) for v in grouped.values())
  need(rate==view['rate'] and counts==view['acceptance_counts'] and proposals==view['draft_proposals'],'stored summary differs from retained evidence')
  for rank in (0,1):
   boundary=read(dest/'boundary'/f'boundary-rank{rank}.json')
   need(boundary['passed'] is True and boundary['total_reset'] is True and boundary['cached_tokens']==0 and boundary['weight_uploads_after_load']==0 and boundary['selection_sha256']==selection['selection_sha256'],'request state reset/selection failed')
  rates.append(rate);all_counts.append(counts);all_proposals.append(proposals)
 need(all(x==all_counts[0] for x in all_counts) and all(x==all_proposals[0] for x in all_proposals),'acceptance/proposal trace differs')
 result=evaluate(rates);result.update(all_views_exact=True,exact_count=65,evidence=pins,bracket_lane='B',chain_lane='A',chain_cards=[0,1]);return result
if __name__=='__main__':print(json.dumps(verify(),indent=2))
