"""Install private harness, frozen inputs and declared storage/wait envelopes."""
import hashlib,json,math,os,resource,shutil
from pathlib import Path
P=Path(__file__).resolve().parent;ROOT=P.parents[3];S=P.parent
resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3))
def sha(p):
 with p.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,r):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(r,indent=2)+'\n')
for name in('two-card','one-card'):
 p=P/name
 for module in('entry','common','conditions','cpu_seal','readiness','screen','worker','measurement','storage'):
  shutil.copy2(P/(module+'.py'),p/(module+'.py'))
 # Canonical CPU oracle order has incident-retrospective; mapping order is identical.
 # Only inputs/identity/plan are consumed at runtime, never a model payload here.
 shutil.copy2(p/'inputs/incident-retrospective/input.json',p/'inputs/input.json')
 shutil.copy2(p/'inputs/incident-retrospective/tokens.txt',p/'inputs/tokens.txt')
 mirrors=p/'native-source/repo'
 constants=[]
 for src in list(mirrors.rglob('*.cpp'))+list(mirrors.rglob('*.hpp')):
  text=src.read_text()
  if 'rope.bf16'not in text and 'mtp-manifest.tsv'not in text:continue
  original=ROOT/src.relative_to(mirrors)
  dirs={original.parent}
  import re
  for match in re.findall(r'^#line \d+ "([^"\n]+)"',text,re.M):
   path=Path(match)
   if path.is_relative_to(mirrors):dirs.add((ROOT/path.relative_to(mirrors)).parent)
  for d in dirs:
   for leaf in('rope.bf16','mtp-manifest.tsv'):
    if(d/leaf).exists():
     target=mirrors/(d/leaf).relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(d/leaf,target)
     constants.append(dict(source=str((d/leaf).relative_to(ROOT)),local=str(target.relative_to(p)),sha256=sha(target),bytes=target.stat().st_size))
 save(p/'runtime-constants.json',constants)
 parent=S/('packet136-record-bundle'if name=='two-card'else'packet58aj-onecard-resident')
 run=parent/('build/device-cards01-a/WS128/run'if name=='two-card'else'evidence/card0-58aj-a/WS128/run')
 sizes={}
 for f in run.rglob('*'):
  if f.is_file()and not f.is_symlink():sizes[str(f.relative_to(run))]=f.stat().st_size
 measured=sum(sizes.values());states=[json.loads(f.read_text())for f in run.rglob('state-retention.json')]
 state=max([r['original_bytes']for r in states]or[0])
 # Upper bound: every retained predecessor byte grows with tokens, plus one raw state.
 scaled=math.ceil(measured*(512/128)*(13/12))+state
 planned=math.ceil(scaled*2)
 cold=[]
 for e in json.loads((p/'oracle128/suite-manifest.json').read_text())['prompts']:
  r=json.loads((p/'evidence/parent-requests'/(e['prompt_id']+'.json')).read_text())
  stamps=r['timing_rows'];first=stamps[0]['completed_monotonic'];start=r.get('request_start_monotonic')
  cold.append((first-start)*1000 if start is not None else r['prompt_wall_ms'])
 maxcold=max(cold)
 wait=1200 if name=='two-card'else 600
 assert wait>=4*maxcold/1000,(name,maxcold)
 budget=dict(measured_parent=str(run.relative_to(ROOT)),measured_parent_retained_bytes=measured,measured_max_raw_state_bytes=state,
  source_sizes=sizes,projection_not_measurement=dict(output_token_scale=4,request_scale=13/12,all_bytes_scaled=True,projected_peak_bytes=scaled),
  planned_write_bytes=planned,multiplier_over_scaled_measured=2,actual_512_write_measurement_pending=True,device_floor_bytes=25_000_000_000,cpu_stop_bytes=27_000_000_000,
  host_required_available_bytes=98_990_252_032 if name=='one-card'else 105_411_248_128,
  wait_seconds=wait,maximum_measured_request_prefill_ms=maxcold,minimum_per_operation_wait_multiple=wait/(maxcold/1000),
  load_watchdog_seconds=7200,expected_seconds=[500,1200]if name=='two-card'else[800,1800],
  no_wall_clock_data_proof_deadline=True,scope='one fresh load; prefill plus12x512. Separate run repeats this reserve; never overlap.')
 save(p/'budget.json',budget)
 print(name,'constants',len(constants),'budget',planned,'maxcold ms',maxcold,flush=True)
