"""Verify final CPU receipts and write READY as the last artifact."""
import json,re,shutil,subprocess
from pathlib import Path
from build_engine import P,ROOT,sha,save
Q=P/'screen';OPS=P.parents[1]/'ops'
def main():
 ready=P/'READY-FOR-DEVICE.json';assert not ready.exists()
 assert not (Q/'evidence/card0-58as-v5-a').exists()
 subprocess.run(['/usr/bin/python3','-B',str(P/'seal.py'),'--verify'],stdin=subprocess.DEVNULL,check=True)
 checks={}
 for leaf in ('cpu-exactness','wait-tests','preparation','analyzer-real-parent','source-delta','flags','queue-plans','shared-entry-report-final','closure-audit'):
  f=P/'evidence'/f'{leaf}.json';r=json.loads(f.read_text());assert r['passed'],leaf;checks[str(f.relative_to(P))]=sha(f)
 prep=json.loads((P/'evidence/preparation.json').read_text());assert prep['real_arm_sequence'] and prep['real_reset_sensors']==130 and prep['requests']==60 and prep['view_resets']==5
 assert prep['peak_child_rss_bytes']<4*1024**3
 assert prep['target_binary_sha256']==sha(P/'build/device/own-rt-iq3')
 assert prep['native_source_sha256']==sha(P/'native/generated/main.cpp')
 assert prep['probe_source_sha256']==sha(P/'native/preparation_probe.cpp')
 exact=json.loads((P/'evidence/cpu-exactness.json').read_text());assert len(exact['records'])==2
 for r in exact['records']:
  assert r['resets']==60 and r['view_resets']==5 and r['real_sensor_samples']==130 and r['all_fixture_bytes_equal']
  assert r['binary_sha256']==sha(P/'build'/r['compiler']/'own-rt-iq3')
 shared=json.loads((P/'evidence/shared-entry-report-final.json').read_text());job=shared['jobs'][0]
 assert all(b['passed'] for b in job['binaries']) and job['report']['passed'] and job['shared_environment_matches']
 assert job['storage_floor']['passed'] and job['wall_deadlines']['passed'] and job['gate_identity']['status']!='FAIL'
 proposal=OPS/'lane-queue/proposed-p58as-v5-A.txt';assert proposal.read_bytes()==(Q/'proposals'/proposal.name).read_bytes()
 plan=json.loads((P/'evidence/queue-plans.json').read_text());assert plan['records'][0]['proposal_sha256']==sha(proposal)
 assert shutil.disk_usage('/').free>=27_000_000_000
 row=dict(schema='own-runtime.packet58as.ready.v1',ready_for_device=True,passed=True,device_executed=False,
  lane='A',scope='whole-host',gpu_count=1,card=0,model_loads=1,windows=['K1a','K1b','WSCREEN'],
  separate_smoke_required=False,opening_contract='No separate smoke: bracket opens with K1a/K1b and exact A0 control.',
  arm_order=['poll','spin','poll','spin','poll'],labels=['A0','B0','A1','B1','A2'],warmup='A0 exact, excluded only from speed and drift',
  prompts_per_view=12,max_new=128,required_exact_requests=60,oracle='iq3-p49-split32-v1',kv_dtype='BF16',resident_lookups_all_views=True,
  winner_minimum_gain_over_every_warm_control=.005,maximum_control_drift_fraction=.03,
  per_operation_wait_seconds=600,spin_budget_microseconds=250,sleep_after_spin_microseconds=20,yield_every_iterations=256,
  device_disk_floor_bytes=25_000_000_000,cpu_disk_stop_bytes=27_000_000_000,host_required_available_bytes=98990252032,
  owner_thread_cpu_utilization='Measured per request by CLOCK_THREAD_CPUTIME_ID; reported per view as percent of one core; pending device run',
  no_wall_clock_data_proof_limits=True,live_checks='stream presence/format and exactness only',native_readers='ionice -c3',
  build_receipt_sha256=sha(Q/'build-receipt.json'),checks=checks,proposals={str(proposal.relative_to(ROOT)):sha(proposal)},
  shared_tool_limitations=['Shared --report passes. Its generic smoke report is synthetic only; no separate smoke row exists.','Shared preparation adapter has no unranked one-card CPU transport probe. Private preparation_gate.py exercised real device argv/plan and all reset paths; synthetic transport/weights, no GPU.'],
  device_exactness='pending',device_speed='pending',fresh_process_repeat=False,strict512=False,submission_eligible=False,
  compile_turns=1,coordinator_requirements='Whole-host lane A; lane B drained/excluded; fresh fault review; no retry; graceful drain; leave cards empty',
  preparation_base_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip())
 save(ready,row)
 print('READY packet58as: CPU checks complete; one-load device kill-test pending')
if __name__=='__main__':main()
