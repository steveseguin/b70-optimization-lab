"""Write final readiness only after every CPU gate and four temporary plans pass."""
import importlib.util,json,shutil
from p157_v5_build_engine import P,LOCAL,ROOT,sha,save,limits
from cpu_seal import verify,check_sources
from readiness import GATES

def main():
 limits();seal=verify();proofs={}
 for name in (*GATES,'loader'):
  path=P/'evidence'/(name+'.json');row=json.loads(path.read_text())
  assert row['passed'] and row['device_executed'] is False,name
  if row.get('sources'):check_sources(row['sources'])
  proofs[name]=sha(path)
 prep=json.loads((P/'evidence/preparation.json').read_text())
 assert prep['argv_origin']=='packet157 real entry interception'
 assert len(prep['rows'])==4 and {r['rank'] for r in prep['rows']}=={0,1}
 plans=json.loads((P/'evidence/queue-plan.json').read_text())
 assert len(plans['rows'])==4 and plans['queued'] is False and plans['live_queue_modified'] is False
 guard=LOCAL.parents[1]/'ops/lane-queue/pin_guard.py'
 spec=importlib.util.spec_from_file_location('final_p157_guard',guard);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 for r in plans['rows']:
  path=ROOT/r['proposal_name'];assert sha(path)==r['sha256'];assert m.check_job(json.loads(path.read_text()))['passed']
 marker=dict(schema='packet157.cpu-ready.v1',passed=True,ready_for_device=True,
  device_executed=False,queued=False,device_quality_pending=True,device_overhead_pending=True,
  device_group_ranking_pending=True,arithmetic='iq3-p49-split32-v1',prefix_rows=80128,
  cpu_seal_sha256=sha(P/'cpu-seal.json'),cpu_gate_sha256=proofs,
  sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'final_ready.py',P/'loader_gate.py',P/'evidence/loader.json']},
  lanes=['A','B'],lane_order=['A','B'],proposals=plans['rows'],
  one_load_order=['control','timed','control','timed','control'],
  expected_seconds=[420,600],watchdog_seconds=2400,planned_writes_per_view=145_000_000,
  planned_writes_smoke=145_000_000,planned_writes_split=725_000_000,
  measured_parent_total_bytes=243_000_000,device_free_floor_bytes=25_000_000_000,
  cpu_preparation_free_floor_bytes=27_000_000_000,root_free_at_seal_bytes=shutil.disk_usage('/').free,
  cpu_peak_rss_kib=prep['peak_rss_kib'],
  limitation='CPU readiness only. No device timing, full-model parity, overhead or measured top-two ranking exists for packet157. Both proposals remain unqueued.')
 save(LOCAL/'READY-FOR-DEVICE.json',marker)  # LAST artifact write.
 for r in plans['rows']:assert m.check_job(json.loads((ROOT/r['proposal_name']).read_text()))['passed']
 print('Packet157 READY: both lanes, A first; four proposals unqueued; device evidence pending')
if __name__=='__main__':main()
