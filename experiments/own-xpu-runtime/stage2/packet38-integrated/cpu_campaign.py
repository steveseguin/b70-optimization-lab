#!/usr/bin/env python3
"""Serial CPU qualification; each stage runs once, fails closed, and records its log."""
import argparse,json,os,subprocess,sys,time
from pathlib import Path
P=Path(__file__).resolve().parent;B=P/'build';PY='/home/steve/.venvs/vllm-xpu/bin/python'
CHEAP=['prepared_unit_gate.py','prepared_host_benchmark.py','p33_candidate_gates.py','test_k2_selection.py','test_k2_admission.py','review_prepared_gate.py','test_submission_overlay.py','argument_state_gate.py','cpu_gates.py','p33_linked_fixture_gate.py','fixture_gate.py','validation_gate.py','entry_codes.py','test_window.py','identity_tree_test.py','capture_gate.py','expert_down_review_gate.py','test_state_machine.py','test_mtp_controller.py','run_fault_gate.py','canary_host_gate.py']
def execute(stage,argv):
 from storage import admit
 admit(550_000_000)
 path=B/('campaign-'+stage+'.log');start=time.monotonic()
 with path.open('w') as out:child=subprocess.Popen(['nice','-n','19','ionice','-c','3',*map(str,argv)],stdout=out,stderr=subprocess.STDOUT)
 peak=0
 while child.poll() is None:
  anon=0
  for proc in Path('/proc').iterdir():
   if not proc.name.isdigit():continue
   try:
    if str(P).encode() not in (proc/'cmdline').read_bytes():continue
    for line in (proc/'status').read_text().splitlines():
     if line.startswith('RssAnon:'):anon+=int(line.split()[1])*1024
   except (OSError,ProcessLookupError):pass
  peak=max(peak,anon)
  if anon>=9_500_000_000:
   child.send_signal(15);raise RuntimeError('packet CPU anonymous memory guard; cooperative stop')
  time.sleep(.2)
 result=dict(stage=stage,returncode=child.returncode,seconds=time.monotonic()-start,peak_packet_anonymous_bytes=peak,log=str(path.relative_to(P)),device_executed=False)
 (B/(stage+'-status.json')).write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
 if child.returncode:raise RuntimeError('CPU gate failed: '+str(path))
 return result

def main():
 ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['cheap','mini','real','real-gnu','real-intel','real-native','draft','captures','draft-final','suite']);ap.add_argument('--start',default='');a=ap.parse_args()
 assert os.getpriority(os.PRIO_PROCESS,0)==19 and os.environ.get('OMP_NUM_THREADS')=='2'
 (B/'tmp').mkdir(exist_ok=True);os.environ['TMPDIR']=str(B/'tmp')
 rows=[]
 if a.phase=='cheap':
  scripts=CHEAP[CHEAP.index(a.start):] if a.start else CHEAP
  for script in scripts:rows.append(execute(script,[PY,'-B',P/script]))
  rows.append(execute('controller-review',[PY,'-B',P/'test_controller_review.py','--output',P/'review-controller-tests.json']))
 elif a.phase=='mini':
  for compiler in ('gnu-host','icpx-host','asan'):
   rows.append(execute('mini-'+compiler,[PY,'-B',P/'gates.py','mini',compiler]))
   rows.append(execute('mtp-'+compiler,[PY,'-B',P/'mtp_gates.py',compiler]))
  rows.append(execute('resident-host',[PY,'-B',P/'resident_host_gate.py']))
 elif a.phase in ('real-gnu','real-intel'):
  compiler='gnu-host' if a.phase=='real-gnu' else 'icpx-host'
  rows.append(execute('real-'+compiler,[PY,'-B',P/'real_campaign.py',compiler]))
 elif a.phase=='real-native':
  rows.append(execute('real-controller',[PY,'-B',P/'real_controller_gate.py']))
  rows.append(execute('rollback-audit',[PY,'-B',P/'audit_rollback.py']))
 elif a.phase=='real':
  for compiler in ('gnu-host','icpx-host'):rows.append(execute('real-'+compiler,[PY,'-B',P/'real_campaign.py',compiler]))
  rows.append(execute('real-controller',[PY,'-B',P/'real_controller_gate.py']))
  rows.append(execute('rollback-audit',[PY,'-B',P/'audit_rollback.py']))
 elif a.phase in ('draft','captures'):
  for name in ('incident-retrospective','code-review','customer-email','benchmark-analysis'):
   rows.append(execute('capture-'+name,[PY,'-B',P/'capture_cpu.py',name]))
   rows.append(execute('rebind-'+name,[PY,'-B',P/'rebind_agreement.py',name]))
  rows.append(execute('draft-auth',[PY,'-B',P/'draft_auth_gate.py']))
  if a.phase=='draft':rows.append(execute('pipeline-draft-agreement',[PY,'-B',P/'pipeline_draft_agreement.py']))
 elif a.phase=='draft-final':rows.append(execute('pipeline-draft-agreement',[PY,'-B',P/'pipeline_draft_agreement.py']))
 else:
  import fcntl
  draft_lock=(B/'cpu-mtp.lock').open('a');fcntl.flock(draft_lock,fcntl.LOCK_EX)
  source=P/'suite-cpu-manifest.json';snapshot=B/'suite-cpu-manifest.json';snapshot.write_bytes(source.read_bytes())
  run=B/('suite-real-'+str(time.time_ns()))
  rows.append(execute('suite-real',[PY,'-B',P/'suite.py','--binary',B/'gnu-host/own-rt-iq3','--output',run,'--suite-manifest',snapshot,'--controller','native','--draft','mtp','--dispatch',P/'dispatch-p38.json','--repeat','1','--context','256','--seconds','172800','--wait-seconds','7200']))
  from suite_export import export_run
  exported=export_run(run,P/'suite-real-cpu.json')
  from storage import discard,archive_files
  exported['scratch_archive']=discard(run)
  rows[-1]['scratch_archive']=exported['scratch_archive']
  log=B/'campaign-suite-real.log'
  if log.exists():
   exported['campaign_log_archive']=archive_files([log],P/'evidence/campaign-suite-real.log.jsonl.gz');log.unlink()
   rows[-1]['log_archive']=exported['campaign_log_archive']
  (P/'suite-real-cpu.json').write_text(json.dumps(exported,indent=2)+'\n')
 (P/('campaign-'+a.phase+'.json')).write_text(json.dumps(dict(passed=True,rows=rows,device_executed=False),indent=2)+'\n')
if __name__=='__main__':main()
