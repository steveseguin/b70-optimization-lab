"""Static logical-access counts, never device timings or speed qualification."""
import json
from pathlib import Path
P=Path(__file__).resolve().parent
def report():
 rows=[]
 for selected in (128,2048):
  current=24*selected*256*2*2;candidate=6*selected*256*2*2
  rows.append(dict(occupied_context=128 if selected==128 else 4096,selected_tokens=selected,production_logical_kv_read_bytes=current,candidate_logical_kv_read_bytes=candidate,logical_global_bytes_removed=current-candidate,added_slm_bytes_per_workgroup=32768,bandwidth_quotient_us_at_assumed_550_GB_s=(current-candidate)/550e9*1e6,host_device_syncs_removed=0,compute_kernel_count_before=3,compute_kernel_count_after=3))
 return dict(schema='packet107.code-cost.v1',device_measured=False,bandwidth_assumption_bytes_per_second=550_000_000_000,qsa=rows,gdn=dict(closed=True,production_norm_trees=1536*2,candidate_norm_trees=16*2,products_removed=(1536-16)*2*128,divisions_removed=(1536-16)*128*3,gate_evaluations_before=1536,gate_evaluations_after=48,production_head_input_bytes=1536*(256*2+12),candidate_head_input_and_preparation_bytes=16*256*2+48*12+(16*256+48*2)*4+1536*(256+2)*4,recurrent_state_read_write_bytes=786432*2*2,host_device_syncs_removed=0,compute_kernel_count_before=1,compute_kernel_count_after=2),limitations=['Logical accesses are not physical DRAM traffic; production may hit caches.','The bandwidth quotient is a conditional arithmetic estimate, not a latency prediction or upper bound on compute savings.','GDN saves repeated math but adds FP32 traffic and one kernel; no credible positive microsecond estimate without measurement.','80 us at 128 tokens cannot be justified by KV bandwidth removal alone.','GDN is closed for exactness, not timing.'])
if __name__=='__main__':
 r=report();(P/'evidence/code-cost.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
