"""Actual launch environment, idle I/O and CPU native arm/reset transport gate (both lanes)."""
import argparse,importlib.util,json,subprocess,time
from pathlib import Path
from build_engine import P,ROOT,limits,sha
import launch_env


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--child',action='store_true');args=ap.parse_args();limits()
 if not args.child:
  command=['/usr/bin/python3','-B',str(Path(__file__).resolve()),'--child']
  result=subprocess.run(command,env=launch_env.environment(),stdin=subprocess.DEVNULL)
  return result.returncode
 import run_micro
 native=run_micro.native_command();assert native[:2]==['/usr/bin/ionice','-c3']
 binary=Path(native[2])
 for lane,proposal in run_micro.PROPOSALS.items():
  job=json.loads(proposal.read_text())
  assert job['lane']==lane==run_micro.parser().parse_args(job['argv'][3:]).lane
  declared=job['plan']['entry_rehearsal']
  assert native[2:]==declared['prepare_probe']['rank_argv'] and sha(binary)==declared['binaries'][0]['sha256']
  assert job['plan']['minimum_root_free_bytes']==25_000_000_000
 assert run_micro.mask('A')['FilterBdfPath']=='0000:23:00.0' and run_micro.mask('B')['FilterBdfPath']=='0000:43:00.0'
 env=dict(launch_env.environment(),**run_micro.mask('B'))
 help_=subprocess.run([str(binary),'--help'],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 flags=[x for x in native[3:] if x.startswith('--')];assert all(x in help_.stdout for x in flags)
 probe='import ctypes,json;v=ctypes.CDLL(None).syscall(252,1,0);assert v>=0;print(json.dumps(dict(io_class=v>>13)))'
 io=subprocess.run([*native[:2],'/usr/bin/python3','-B','-c',probe],env=env,stdin=subprocess.DEVNULL,capture_output=True,text=True,check=True)
 priority=json.loads(io.stdout);assert priority['io_class']==3
 spec=importlib.util.spec_from_file_location('p175_entry_sandbox',P.parents[1]/'ops/rehearse_entry.py');sandbox=importlib.util.module_from_spec(spec);spec.loader.exec_module(sandbox)
 output=P/'evidence'/('prepare-'+str(time.time_ns()));output.mkdir()
 env['ENTRY_PREPARE_OUTPUT']=str(output)
 with (output/'stdout.log').open('x') as out,(output/'stderr.log').open('x') as err:
  # ionice was checked above; Landlock confines the device-defined ELF itself.
  result=subprocess.run(native[2:],env=env,stdin=subprocess.DEVNULL,stdout=out,stderr=err,preexec_fn=lambda:sandbox.prepare_restrict(binary,[],output))
 assert result.returncode==0,(output/'stderr.log').read_text()
 assert 'PASS CPU preparation before first device call' in (output/'stdout.log').read_text()
 rows=[json.loads(x) for x in (output/'real-arm-sensors.jsonl').read_text().splitlines()]
 expected=[(layer,31,0,arm) for layer in (0,3) for arm in (0,1)]
 expected=[x for layer in (0,3) for x in [(layer,31,0,0),(layer,31,0,1)]+[(layer,31,rep+1,(rep+j)%2) for rep in range(240) for j in range(2)]]
 assert [(r['layer'],r['position'],r['repeat'],r['arm']) for r in rows]==expected
 for layer in (0,3):
  chosen=[r for r in rows if r['layer']==layer]
  assert len({r['allocation_identity'] for r in chosen})==1 and len({r['state_sample_sha256'] for r in chosen})==1
 assert all(r['disk_free_bytes']>=27_000_000_000 and r['max_rss_bytes']<=4*1024**3 and r['free_ram_bytes']>0 for r in rows)
 assert all(rows[i+1]['prepare_steps']>rows[i]['prepare_steps'] for i in range(len(rows)-1))
 # Arm B traverses the warm-ahead call sites: its passes take more preparation steps than arm A.
 steps={}
 for i in range(len(rows)-1):
  if rows[i]['layer']==rows[i+1]['layer']:steps.setdefault((rows[i]['layer'],rows[i]['arm']),set()).add(rows[i+1]['prepare_steps']-rows[i]['prepare_steps'])
 assert all(len(v)==1 for v in steps.values()) and all(min(steps[(l,1)])>min(steps[(l,0)]) for l in (0,3))
 digests={lane:sha(path) for lane,path in run_micro.PROPOSALS.items()}
 receipt=dict(passed=True,device_executed=False,model_reads=False,real_sensors=True,real_resets=True,synthetic_weight_transport=True,arithmetic_gate=False,reset_count=len(rows),proposal_sha256=digests,native_sha256=sha(binary),io_priority=priority,checked_flags=flags,actual_environment=env,sensors_sha256=sha(output/'real-arm-sensors.jsonl'),output=str(output.relative_to(ROOT)))
 (P/'evidence/preparation.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(dict(passed=True,reset_count=len(rows))));return 0
if __name__=='__main__':raise SystemExit(main())
