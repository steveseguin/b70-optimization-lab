"""Per-rank modeled admission for unchanged packet150 allocations; no payload read."""
import json,resource
from p157_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

def main():
 limits();rows=[]
 for mode in ('off','split'):
  path=P/'lineage'/mode/'memory-plan.json';plan=json.loads(path.read_text())
  for rank in plan['placements']['1']['capacities']['4096']['ranks']:
   # Retain packet150's private exchange allocations although unreachable here.
   device=rank['arena_device_bytes']+65536
   physical=rank['total_with_mtp_bytes']+65536
   assert device<plan['arena_limit_bytes'] and plan['capacity_bytes']-physical>=plan['minimum_free_bytes']
   rows.append(dict(mode=mode,rank=rank['rank'],modeled_device_bytes=device,
     modeled_physical_bytes=physical,arena_headroom_bytes=plan['arena_limit_bytes']-device,
     physical_headroom_bytes=plan['capacity_bytes']-physical,model_plan_sha256=sha(path),
     device_measured=False,additional_packet157_device_bytes=0,scope_host_budget_bytes=16*1024**2))
 save(P/'evidence/admission.json',dict(passed=True,device_executed=False,rows=rows,
   model_payload_read=False,full_shape_read=False,
   limitation='Rechecked unchanged allocation plan, not fresh full-shape or driver residency evidence.',
   sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'admission_gate.py',*[P/'lineage'/m/'memory-plan.json' for m in ('off','split')]]}))
if __name__=='__main__':
 resource.setrlimit(resource.RLIMIT_AS,(4*1024**3,4*1024**3));main()
