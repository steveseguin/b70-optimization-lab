"""Cached CPU proof plus fast selected imports/admission/consumers/window plans.

Coordinator code is bound by ready.json, not by this expensive CPU proof.
Changing --pin never changes the cached proof or compiler identity.
"""
import argparse,json,os,subprocess,sys,time
from build_engine import P,ROOT,B,limits,sha,save
from chain_seal import check_map
def verify():
 r=json.loads((P/'evidence/dry-run.json').read_text());assert r['passed'] and not r['device_executed'];check_map(ROOT,r['sources']);return r
def cached():
 from prepare_packet import proof
 build,reports,sources=proof()
 # Per-selected-view seals and mutable selection files never enter this cache.
 from bundle_selection import configurations,views
 size=sum(f.stat().st_size for f in B.rglob('*') if f.is_file() and not f.is_symlink());assert size<1500000000
 save(P/'evidence/dry-run.json',dict(passed=True,device_executed=False,sources=sources,compositions=len(views()),configurations=len(configurations()),build_logical_bytes=size,scope='Cached arithmetic, full-shape post-load, memory, miniature/native and protocol proof; selected plans are separate'))
def selected_check():
 started=time.monotonic();verify();from bundle_selection import selected,view_path
 choice=selected();view=view_path(choice)
 env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTHONPATH='/home/steve/.venvs/deepseek-v4-xpu/lib/python3.12/site-packages',TMPDIR=str(B/'tmp'),OMP_NUM_THREADS='2')
 commands=[('imports',[sys.executable,'-B','-c',"import runpy;from bootstrap import install,WRAPPER;install();runpy.run_path(str(WRAPPER/'tp2_worker.py'),run_name='cpu_import');from lane_admission import admission_scope;assert admission_scope('A','screen')=='lane-A';assert admission_scope('A','WS128')=='whole-host'"]),('consumers',[sys.executable,'-B','-m','pytest','-q','-p','no:cacheprovider',str(P/'test_packet91.py'),str(P/'test_lane_admission.py')]),('windows',[sys.executable,'-B',str(P/'plan_gate.py')])]
 for lane in ('A','B'):
  commands.append(('screen-'+lane,[sys.executable,'-B',str(P/'run_screen.py'),'--profile','tp2','--lane',lane,'--placement',choice['placement'],'--lineage',str(view),'--seal',str(view/'screen-seal.json'),'--output',str(P.parent/'screen/v4-lanes/evidence'/('p91-selection-plan-'+lane)),'--plan']))
 rows=[]
 for label,cmd in commands:
  with (P/'evidence'/('selected-'+label+'.log')).open('w') as log:r=subprocess.run(cmd,cwd=P,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,env=env,timeout=240)
  assert r.returncode==0,label+' failed';rows.append(dict(name=label,command=cmd,sha256=sha(P/'evidence'/('selected-'+label+'.log'))))
 elapsed=time.monotonic()-started;assert elapsed<300,'selection rehearsal exceeded five minutes'
 save(P/'evidence/selection-dry-run.json',dict(passed=True,device_executed=False,selection=choice,checks=rows,seconds=elapsed,cached_proof_sha256=sha(P/'evidence/dry-run.json')))
 print('Selected full rehearsal PASS in',round(elapsed,2),'seconds')
def main():
 limits();ap=argparse.ArgumentParser();ap.add_argument('--verify',action='store_true');ap.add_argument('--cached',action='store_true');a=ap.parse_args()
 if a.cached:cached()
 elif a.verify:verify();print('Cached full CPU proof verified')
 else:selected_check()
if __name__=='__main__':main()
