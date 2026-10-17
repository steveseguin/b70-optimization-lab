#!/usr/bin/env python3
"""Reserve the bounded private backup inside unchanged 30 GiB/1.5 GB gates."""
import hashlib,json
from pathlib import Path
P=Path(__file__).resolve().parent;BASE=P.with_name('packet61x-spin-hcfusion-wait')
def main():
 assert not (P/'screen-seal.json').exists()
 plan=json.loads((BASE/'memory-plan.json').read_text());row=plan['placements']['1-split23']['capacities']['4096']['ranks'][1]
 extra=32*1024**2
 for key in ('draft_scratch_controls_buffers_bytes','draft_total_bytes','arena_device_bytes','total_with_mtp_bytes'):row[key]+=extra
 for key in ('arena_headroom_bytes','free_with_mtp_bytes'):row[key]-=extra
 plan['packet66_probe_reserve']=dict(bytes=extra,scope='rank1, split23, context4096 only',bounds='mtp.hpp refuses a larger snapshot',weights_duplicated=False,host_pinned_extra_bytes=0,baseline_sha256=hashlib.sha256((BASE/'memory-plan.json').read_bytes()).hexdigest())
 from memory_gate import configuration
 configuration(plan,4096,1,23)
 (P/'memory-plan.json').write_text(json.dumps(plan,indent=2)+'\n')
 (P/'evidence/memory.json').write_text(json.dumps(dict(passed=True,device_executed=False,extra_bytes=extra,rank1=row),indent=2)+'\n')
 print('rank1 arena headroom',row['arena_headroom_bytes'],'free',row['free_with_mtp_bytes'])
if __name__=='__main__':main()
