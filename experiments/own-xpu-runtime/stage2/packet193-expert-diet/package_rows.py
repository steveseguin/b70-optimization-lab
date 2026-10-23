"""Write the ONE lane-B micro row (PROPOSAL ONLY, never queued) and seal (plan after seal).

  1. proposals/proposed-p193-micro-B.txt (packet mirror) and ops/lane-queue/proposed-p193-micro-B.txt
  2. cpu_seal.py --seal (includes the proposal)
  3. evidence/package-rows.json
Queue files and PAUSE/STOP latches are never touched. Run: nice -n 19 taskset -c 8-15,24-31 python3 -B package_rows.py </dev/null
"""
import json,shutil,subprocess,sys
from pathlib import Path
from build_engine import P,ROOT,EV,LINEAGE,limits,sha,rel,read,save
import run_micro
NAME='proposed-p193-micro-B.txt';LIVE=P.parents[1]/'ops/lane-queue'/NAME;MIRROR=P/'proposals'/NAME;JOB='packet193-expert-diet-micro-B'
def main():
 limits()
 if (P/'READY-FOR-DEVICE.json').exists():sys.exit('READY-FOR-DEVICE.json exists: withdraw it (rename to evidence/withdrawn-ready-<ts>.json) before repackaging')
 build=read(EV/'build.json');modes={r['mode']:r for r in build['records']};adm=read(EV/'admission.json');native=run_micro.native_command()
 sources={rel(P/n):sha(P/n) for n in ('micro.cpp','p193_diet.hpp','run_micro.py','s193_report.py','report-contract.json')}
 job=dict(name=JOB,lane='B',argv=['/usr/bin/python3','-B',rel(P/'run_micro.py'),'--run','--lane','B','--fault-review','{REVIEW}','--authorized-device-window'],env_extra={},
  review='experiments/own-xpu-runtime/stage2/screen/v4-lanes/fault_review.py',planned_write_bytes=run_micro.PLANNED_WRITE_BYTES,
  plan=dict(diagnostic_only=True,measurement_only=True,speed_claim=False,expected_seconds=adm['duration']['expected_seconds'],watchdog_seconds=run_micro.WATCHDOG,
   minimum_root_free_bytes=25_000_000_000,host_required_available_bytes=10*1024**3,device_bytes_upper_bound=run_micro.DEVICE_BYTES_UPPER_BOUND,device_peak_bytes=adm['device']['peak_bytes'],
   model_load=False,physical_card=2,candidates=run_micro.CANDIDATES,
   entry_rehearsal=dict(kind='micro',report_contract='report-contract.json',
    binaries=[dict(path=modes['device']['path'],sha256=modes['device']['sha256'],args=['--help'],contains='usage')],
    prepare_probe=dict(command=native,rank_argv=native,sha256=modes['device']['sha256'],contains='PASS CPU preparation before first device call',metadata=[rel(LINEAGE/'routes-p100b.json')],sources=sources))))
 header=('# PROPOSAL ONLY (packet193). Never queued by preparation; the lane-B window driver decides. Lane B, physical card 2 (0000:43:00.0); the owner\'s\n'
  '# endpoints are stopped by the window driver (whole-host admission). MICRO: exact instruction-diet candidates exp-diet / exp-act-epilogue (gate/up)\n'
  '# and down-diet (down) vs the record kernels: device byte identity on all 384 real routes + NaN/invalid/exceptional fixtures BEFORE timing, then cold\n'
  f"# (384 routes, 512 MiB scrub) and warm strata interleaved in both orders; gate <= 0.85x. No model load; device peak {adm['device']['peak_bytes']:,} B (< 1.2 GB);\n"
  f"# host admission 10 GiB; expected {adm['duration']['expected_seconds']} s; watchdog 1800 s; writes 96 MiB. Never an engine speed result.\n")
 body=header+json.dumps(job)+'\n';MIRROR.parent.mkdir(exist_ok=True);MIRROR.write_text(body);shutil.copyfile(MIRROR,LIVE);assert sha(LIVE)==sha(MIRROR)
 r=subprocess.run([sys.executable,'-B',str(P/'cpu_seal.py'),'--seal'],cwd=ROOT,stdin=subprocess.DEVNULL,capture_output=True,text=True)
 if r.returncode:sys.exit('seal failed:\n'+r.stdout[-2000:]+r.stderr[-2000:])
 save(EV/'package-rows.json',dict(passed=True,device_executed=False,queued=False,live_queue_modified=False,proposal=rel(LIVE),proposal_sha256=sha(LIVE),mirror=rel(MIRROR),
  cpu_seal=rel(EV/'cpu-seal.json'),cpu_seal_sha256=sha(EV/'cpu-seal.json'),rows=[dict(job=JOB,lane='B',expected_seconds=job['plan']['expected_seconds'],watchdog_seconds=job['plan']['watchdog_seconds'],
   host_required_available_bytes=job['plan']['host_required_available_bytes'],device_peak_bytes=job['plan']['device_peak_bytes'],planned_write_bytes=job['planned_write_bytes'],candidates=run_micro.CANDIDATES)]))
 print('package_rows: proposal',rel(LIVE),sha(LIVE)[:16],'sealed;',r.stdout.strip())
if __name__=='__main__':main()
