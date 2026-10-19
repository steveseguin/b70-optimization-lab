"""CPU-only final checks. READY is written last and never hides failed gates."""
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
from analyze import limits
from micro_analyze import check_bytes,SHAPES
P=Path(__file__).resolve().parent
ROOT=P.parents[3]
OPS=P.parents[1]/'ops'
E=P/'evidence/micro-prep'
PROPOSAL=OPS/'lane-queue/proposed-p162-micro-B.txt'
def sha(path):
 with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def read(path):return json.loads(Path(path).read_text())
def save(path,value):Path(path).write_text(json.dumps(value,indent=2)+'\n')
def main():
 limits()
 marker=P/'READY-FOR-DEVICE.json'
 if marker.exists():
  archive=E/'attempts';archive.mkdir(exist_ok=True)
  marker.rename(archive/('readiness-'+sha(marker)+'.json'))
 import run_micro
 identity=run_micro.build_gate()
 proof=read(E/'build.json')
 comparisons=[]
 for name,shapes in [('synthetic',('synthetic',)),('real',SHAPES)]:
  path=E/(name+'-cpu.jsonl');rows=[json.loads(s) for s in path.read_text().splitlines()]
  exact,nan=check_bytes(rows,shapes);assert exact
  comparisons.append(dict(source=name,finite_bytes_equal=exact,nan_input_behavior=nan,stream_sha256=sha(path)))
 with (E/'analyzer-tests.log').open('w') as log:
  subprocess.run([sys.executable,'-B',str(P/'test_micro.py')],stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,check=True)
 assert read(E/'parser-tests.json')['binary_sha256']==sha(P/'build/micro-device')
 command=[sys.executable,'-B',str(OPS/'rehearse_entry.py'),str(PROPOSAL),'--report','--json']
 with (E/'entry-report.json').open('w') as out,(E/'entry-report.log').open('w') as err:
  entry=subprocess.run(command,stdin=subprocess.DEVNULL,stdout=out,stderr=err)
 shared=read(E/'entry-report.json');job=shared['jobs'][0]
 assert all(job[k]['passed'] for k in ('storage_floor','wall_deadlines','preparation_path','gate_identity'))
 assert all(r['passed'] for r in job['binaries'])
 with tempfile.TemporaryDirectory(prefix='p162b-plan-') as tmp:
  d=Path(tmp);(d/'queue-B.txt').write_bytes(PROPOSAL.read_bytes())
  cp=subprocess.run([sys.executable,'-B',str(OPS/'lane-queue/lanequeue.py'),'plan','--lane','B','--directory',str(d)],stdin=subprocess.DEVNULL,capture_output=True,text=True)
  (E/'queue-plan.log').write_text(cp.stdout+cp.stderr);assert cp.returncode==0
  save(E/'queue-plan.json',dict(passed=True,temporary_copy=True,live_queue_edited=False,returncode=0))
 save(E/'validation.json',dict(cpu_preparation_passed=True,device_executed=False,model_output_claim=False,
      identity=identity,comparisons=comparisons,analyzer_tests_passed=True,packet_report_path_tested=True,
      shared_entry_command=command,shared_entry_returncode=entry.returncode,
      shared_report_passed=job['report']['passed'],temporary_plan_passed=True,
      production_header_equal=(P.parent/'packet136-record-bundle/p90_expert.hpp').read_bytes()==(P.parent/'packet131-snapshot-banks/p90_expert.hpp').read_bytes()))
 # Bind the real native dependency closure, Python supervision/report closure,
 # proposal, real row hashes, test receipts and historical NaN evidence.
 files={PROPOSAL,*P.glob('*.py'),*P.glob('*.hpp'),P/'micro.cpp',P/'MICRO162B.md',P/'README.md',P/'DO-NOT-REPEAT.md',P/'RETENTION.md',*E.glob('*')}
 for r in proof['records']:
  files.add(ROOT/r['binary']);files.update(ROOT/n for n in r['sources'])
 for r in read(E/'inputs.json')['records']:files.add(ROOT/r['path'])
 for mod in list(sys.modules.values()):
  name=getattr(mod,'__file__',None)
  if name:
   path=Path(name).resolve()
   if (path.is_relative_to(P) or path.is_relative_to(run_micro.WRAPPER)) and path.is_file() and path.suffix=='.py':files.add(path)
 ready=bool(shared['passed'] and entry.returncode==0)
 result=dict(schema='packet162b.diagnostic-readiness.v1',ready=ready,diagnostic_only=True,
    device_executed=False,queued=False,model_output_claim=False,device_speed=None,
    blockers=[] if ready else ['required shared --report lacks a standalone micro report adapter; frozen ops were not changed'],
    packet_report_tests_passed=True,shared_report_passed=job['report']['passed'],
    finite_cpu_bytes_equal=True,nan_chain_parity_resolved=False,full_build_authorized=False,
    sources={str(f.relative_to(ROOT)):sha(f) for f in sorted(files) if f.is_file()})
 # Must be the last artifact write in this entry.
 save(P/'READY-FOR-DEVICE.json',result)
 print(json.dumps(dict(ready=ready,blockers=result['blockers'],cpu_preparation_passed=True,queued=False)))
if __name__=='__main__':main()
