"""Actual launch environment, idle I/O and CPU native arm/reset transport gate."""
import argparse,importlib.util,json,os,resource,subprocess,sys,tempfile,time
from pathlib import Path
from build_engine import P,ROOT,limits,sha
import launch_env

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--child',action='store_true');args=ap.parse_args();limits()
 proposal=P.parents[1]/'ops/lane-queue/proposed-p166-micro-B.txt';job=json.loads(proposal.read_text())
 if not args.child:
  command=['/usr/bin/python3','-B',str(Path(__file__).resolve()),'--child']
  result=subprocess.run(command,env=launch_env.environment(),stdin=subprocess.DEVNULL)
  return result.returncode
 import run_micro
 assert job['lane']==run_micro.parser().parse_args(job['argv'][3:]).lane
 declared=job['plan']['entry_rehearsal'];native=run_micro.native_command()
 assert native[:2]==['/usr/bin/ionice','-c3']
 assert native[2:]==declared['prepare_probe']['rank_argv']
 binary=Path(native[2]);assert sha(binary)==declared['binaries'][0]['sha256']
 env=dict(launch_env.environment(),**run_micro.MASK)
 help_=subprocess.run([str(binary),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 flags=[x for x in native[3:] if x.startswith('--')];assert all(x in help_.stdout for x in flags)
 probe='import ctypes,json;v=ctypes.CDLL(None).syscall(252,1,0);assert v>=0;print(json.dumps(dict(io_class=v>>13)))'
 io=subprocess.run([*native[:2],'/usr/bin/python3','-B','-c',probe],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 priority=json.loads(io.stdout);assert priority['io_class']==3
 spec=importlib.util.spec_from_file_location('p166_entry_sandbox',P.parents[1]/'ops/rehearse_entry.py');sandbox=importlib.util.module_from_spec(spec);spec.loader.exec_module(sandbox)
 output=P/'evidence'/('prepare-'+str(time.time_ns()));output.mkdir()
 env['ENTRY_PREPARE_OUTPUT']=str(output)
 with (output/'stdout.log').open('x') as out,(output/'stderr.log').open('x') as err:
  # ionice was checked above; Landlock confines the device-defined ELF itself.
  result=subprocess.run(native[2:],env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,preexec_fn=lambda:sandbox.prepare_restrict(binary,[],output))
 assert result.returncode==0,(output/'stderr.log').read_text()
 assert 'PASS CPU preparation before first device call' in (output/'stdout.log').read_text()
 rows=[json.loads(x) for x in (output/'real-arm-sensors.jsonl').read_text().splitlines()]
 expected=[(layer,pos,rep,j if rep==0 else (rep-1+j)%2) for layer in (0,3) for pos in (2,3,31) for rep in range(201) for j in range(2)]
 assert [(r['layer'],r['position'],r['repeat'],r['arm']) for r in rows]==expected
 for layer in (0,3):
  chosen=[r for r in rows if r['layer']==layer]
  assert len({r['allocation_identity'] for r in chosen})==1
  for pos in (2,3,31):assert len({r['state_sample_sha256'] for r in chosen if r['position']==pos})==1
 assert all(r['disk_free_bytes']>=27_000_000_000 and r['max_rss_bytes']<=4*1024**3 and r['free_ram_bytes']>0 for r in rows)
 assert all(rows[i+1]['prepare_steps']>rows[i]['prepare_steps'] for i in range(len(rows)-1))
 receipt=dict(passed=True,device_executed=False,model_reads=False,real_sensors=True,real_resets=True,synthetic_weight_transport=True,arithmetic_gate=False,reset_count=len(rows),proposal_sha256=sha(proposal),native_sha256=sha(binary),io_priority=priority,checked_flags=flags,actual_environment=env,sensors_sha256=sha(output/'real-arm-sensors.jsonl'),output=str(output.relative_to(ROOT)))
 (P/'evidence/preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
