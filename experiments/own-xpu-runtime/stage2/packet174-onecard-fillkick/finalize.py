"""Verify final CPU receipts and write READY as the last artifact (packet174)."""
import json,shutil,subprocess
from pathlib import Path
from build_engine import P,ROOT,sha,save
Q=P/'screen';OPS=P.parents[1]/'ops'
CHECKS=('fill-kick','cpu-exactness','wait-tests','preparation','analyzer-real-parent','flags','entry-imports','queue-plans','shared-entry-report-final','pin-guard','fillkick-delta-test')
def main():
 ready=P/'READY-FOR-DEVICE.json';assert not ready.exists()
 assert not (Q/'evidence/card0-174-v5-a').exists()
 subprocess.run(['/usr/bin/python3','-B',str(P/'seal.py'),'--verify'],stdin=subprocess.DEVNULL,check=True)
 checks={}
 for leaf in CHECKS:
  f=P/'evidence'/f'{leaf}.json';r=json.loads(f.read_text());assert r['passed'] is True and r['device_executed'] is False,leaf;checks[str(f.relative_to(P))]=sha(f)
 kick=json.loads((P/'evidence/fill-kick.json').read_text());assert kick['fails_on_old_code'] and len(kick['records']['parser'])==5 and len(kick['records']['exactness'])==6
 prep=json.loads((P/'evidence/preparation.json').read_text());assert prep['real_arm_sequence'] and prep['real_reset_sensors']==130 and prep['requests']==60 and prep['view_resets']==5
 assert prep['peak_child_rss_bytes']<4*1024**3
 assert prep['target_binary_sha256']==sha(P/'build/device/own-rt-iq3')
 assert prep['native_source_sha256']==sha(P/'native/generated/main.cpp')
 exact=json.loads((P/'evidence/cpu-exactness.json').read_text());assert len(exact['records'])==2
 for r in exact['records']:
  assert r['resets']==60 and r['view_resets']==5 and r['real_sensor_samples']==130 and r['all_fixture_bytes_equal']
  assert r['binary_sha256']==sha(P/'build'/r['compiler']/'own-rt-iq3')
 analyzer=json.loads((P/'evidence/analyzer-real-parent.json').read_text())
 assert [r['name'] for r in analyzer['records']]==['packet58as','packet171b'] and all(r['readback_linear_in_same_token_fill_bytes'] for r in analyzer['records'])
 shared=json.loads((P/'evidence/shared-entry-report-final.json').read_text())
 proposal=OPS/'lane-queue/proposed-p174-v5-A.txt';assert proposal.read_bytes()==(Q/'proposals'/proposal.name).read_bytes()
 plan=json.loads((P/'evidence/queue-plans.json').read_text());assert plan['records'][0]['proposal_sha256']==sha(proposal)
 assert shared['proposal_sha256']==sha(proposal)
 assert shutil.disk_usage('/').free>=27_000_000_000
 row=dict(schema='own-runtime.packet174.ready.v1',ready_for_device=True,passed=True,device_executed=False,
  packet='packet174-onecard-fillkick',job='packet174-v5-A',proposal=str(proposal.relative_to(ROOT)),proposal_sha256=sha(proposal),
  lane='A',scope='whole-host',gpu_count=1,card=0,model_loads=1,windows=['K1a','K1b','WSCREEN'],
  separate_smoke_required=False,opening_contract='No separate smoke: bracket opens with K1a/K1b and exact A0 control.',
  arm_order=['spin','spin-kick','spin','spin-kick','spin'],labels=['A0','B0','A1','B1','A2'],
  arms=dict(A='packet58as spin parent (--fill-kick off)',
            B='spin plus one non-blocking zeCommandListHostSynchronize(maintenance list, 0) after each non-empty fill batch (--fill-kick on)'),
  process_wide_option='--fill-kick off|on (default off); accepted with every engine chain window argv (KD, W2m, WS, WS128x, WS128); the bracket per-view selection sets the same p174::fill_kick switch',
  warmup='A0 exact, excluded only from speed and drift',
  prompts_per_view=12,max_new=128,required_exact_requests=60,oracle='iq3-p49-split32-v1',kv_dtype='BF16',resident_lookups_all_views=True,
  winner_minimum_gain_over_every_warm_control=.005,maximum_control_drift_fraction=.03,
  mechanism_readout='summary.json mechanism_readout: slow-readback fraction, readback ms per same-token fill MB, fill MB per token, decode hit rate, kicks; kept on every outcome',
  decision_rule='B wins and the readback slope collapses: fills were waiting for a host synchronization; port --fill-kick on to the record chain. B neutral and slope persists: close; fill execution is gated below the host flush (next: fill volume or kernel-store tail readback, priced in notes/2026-10-19-own-runtime-packet174.md).',
  unchanged=['which experts are planned, filled, evicted and published, and when','kernels','arithmetic','selection','spin policy','resident lookups','foreground copies'],
  per_operation_wait_seconds=600,spin_budget_microseconds=250,sleep_after_spin_microseconds=20,yield_every_iterations=256,
  device_disk_floor_bytes=25_000_000_000,cpu_disk_stop_bytes=27_000_000_000,host_required_available_bytes=98990252032,
  no_wall_clock_data_proof_limits=True,live_checks='stream presence/format and exactness only',native_readers='ionice -c3',
  build_receipt_sha256=sha(Q/'build-receipt.json'),checks=checks,
  shared_tool_limitations=shared['shared_tool_limitations'],
  device_exactness='pending',device_speed='pending',fresh_process_repeat=False,strict512=False,submission_eligible=False,
  compile_turns=1,coordinator_requirements='Whole-host lane A; lane B drained/excluded; fresh fault review; no retry; graceful drain; leave cards empty',
  parent=dict(name='packet58as-onecard-spinwait',parent_relpath='experiments/own-xpu-runtime/stage2/packet58as-onecard-spinwait',parent_commit=json.loads((P/'lineage/packet174-copy.json').read_text())['parent']['parent_commit']),
  preparation_head_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip())
 save(ready,row)
 print('READY packet174: CPU checks complete; one-load device kill-test pending')
if __name__=='__main__':main()
