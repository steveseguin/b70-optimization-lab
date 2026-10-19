"""CPU-only validation/reseal; write the final readiness marker last."""
from datetime import datetime, timezone
import json
from pathlib import Path
import resource
import subprocess
import sys
import tempfile
from build_engine import P, ROOT, limits, sha, save

OPS=P.parents[1]/'ops'
PROPOSALS=[OPS/'lane-queue'/n for n in ('proposed-p58ai-census-A.txt','proposed-p58ai-census5-A.txt')]

def run(argv, name, expected=0, bounded=True):
    def cap(): resource.setrlimit(resource.RLIMIT_AS,(2*1024**3,2*1024**3))
    with (P/'evidence'/name).open('w') as output, (P/'evidence'/(name+'.stderr.log')).open('w') as errors:
        cp=subprocess.run(['/usr/bin/python3','-B',*map(str,argv)],cwd=ROOT,
            stdin=subprocess.DEVNULL,stdout=output,stderr=errors,timeout=180,
            preexec_fn=cap if bounded else None)
    if cp.returncode != expected: raise RuntimeError('check failed: '+name)

def main():
    limits()
    marker=P/'READY-FOR-DEVICE.json'
    if marker.exists():
        # Withdraw stale readiness during resealing; retain its original bytes.
        (P/'evidence'/('p58aid-prior-ready-'+sha(marker)+'.json')).write_bytes(marker.read_bytes())
        marker.unlink()
    run([P/'run_cpu_gates.py'],'p58aid-cpu-gates.log',bounded=False)
    run([P/'first_request_gate.py'],'p58aid-first-request.log')
    run([OPS/'rehearse_entry.py',PROPOSALS[1],'--report','--json'],'p58aid-census5-rehearse.json')
    # Actual parent cold timings calibrate waits, not this packet's performance.
    parent=P.parent/'packet58ad-onecard-record/evidence/card0-58ad-a/WS128/run/summary.json'
    measured=json.loads(parent.read_text())
    cold=max(r['ttft_ms'] for r in measured['requests'])/1000
    assert 600 >= 4*cold
    save(P/'evidence/p58aid-wait-policy.json',dict(passed=True,device_executed=False,
        timing_source=str(parent.relative_to(ROOT)),timing_source_sha256=sha(parent),
        measured_parent_max_ttft_seconds=cold,per_operation_wait_seconds=600,
        minimum_multiplier=4,actual_multiplier=600/cold,first_request_wall_deadline_seconds=None,
        census_rechecks_fresh_smoke_cold_phase=True,
        scope='Existing native --wait-seconds controls operation waits; no data-proof timeout. Cleanup retains existing cooperative ownership rules.'))
    import analyze
    historical=P/'evidence/card0-census-c/smoke'
    try: analyze.analyze(historical)
    except ValueError as error: reason=str(error)
    else: raise AssertionError('failed device evidence accepted')
    save(P/'evidence/p58aid-real-device-analyzer.json',dict(passed=True,device_executed=False,
        evidence_origin='real failed c-smoke device run',historical_root=str(historical.relative_to(P)),
        queue_sha256=sha(historical/'queue.json'),window_sha256=sha(historical/'WSCREEN/window.json'),
        historical_run_rejected=True,reason=reason,positive_device_census_validation='pending fresh d-smoke',
        positive_validation_required_by='verify_ready.py: all 12 real smoke streams before census5'))
    run([P/'seal.py'],'p58aid-seal.json')
    run([P/'seal.py','--verify'],'p58aid-seal-verify.json')
    sys.path.insert(0,str(OPS/'lane-queue'))
    import pin_guard
    jobs=[json.loads(next(x for x in p.read_text().splitlines() if x.startswith('{'))) for p in PROPOSALS]
    pin_rows=[];plans=[]
    for i,(proposal,job) in enumerate(zip(PROPOSALS,jobs)):
        pin_rows.append(pin_guard.check_job(job))
        with tempfile.TemporaryDirectory(prefix='p58aid-plan-') as tmp:
            directory=Path(tmp)
            (directory/'queue-A.txt').write_bytes(proposal.read_bytes())
            (directory/'queue-B.txt').write_text('# empty CPU plan only\n')
            name=f'p58aid-queue-plan-{i}.log'
            run([OPS/'lane-queue/lanequeue.py','plan','--lane','A','--directory',directory],name)
            rows=[json.loads(line) for line in (P/'evidence'/name).read_text().splitlines() if line.startswith('{')]
            assert len(rows)==1 and rows[0]['plan']=='passed'
            plans.extend(rows)
    save(P/'evidence/p58aid-pin-admission.json',dict(passed=True,device_executed=False,jobs=pin_rows))
    save(P/'evidence/p58aid-queue-plans.json',dict(passed=True,device_executed=False,jobs=plans))
    run([P/'verify_ready.py'],'p58aid-census5-conditional.json',expected=1)
    conditional=json.loads((P/'evidence/p58aid-census5-conditional.json').read_text())
    assert conditional['ready'] is False and 'card0-census-d/smoke/queue.json' in conditional['reason']
    reports=[json.loads((P/'evidence'/n).read_text()) for n in ('shared-entry-report.json','p58aid-census5-rehearse.json')]
    assert all(report['passed'] for report in reports)
    warnings=[dict(job=r['job'],check=key,detail=value) for report in reports for r in report['jobs']
              for key,value in r.items() if isinstance(value,dict) and value.get('status')=='WARN']
    rss=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024
    assert rss < 2*1024**3
    save(P/'evidence/p58aid-resources.json',dict(passed=True,device_executed=False,peak_child_rss_bytes=rss,
        maximum_bytes=2*1024**3,gguf_reads=False,gpu_used=False,services_started=False))
    evidence=['evidence/'+n for n in ('device-import-gate.json','argument-gate.json','python-tests.json',
        'shared-entry-report.json','p58aid-census5-rehearse.json','p58aid-wait-policy.json',
        'p58aid-real-device-analyzer.json','p58aid-pin-admission.json','p58aid-queue-plans.json',
        'p58aid-census5-conditional.json','p58aid-resources.json','first-request-data-gate.json')]
    smoke,census=jobs
    row=dict(schema='own-runtime.packet58ai.prepared.v1',utc=datetime.now(timezone.utc).isoformat(),
        prepared_against_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,stdin=subprocess.DEVNULL).strip(),
        ready_for_device=True,smoke_ready=True,census5_ready=False,census5_conditional=True,
        readiness_scope='CPU-prepared fresh smoke; census5 requires exact d-smoke and real analyzer validation via verify_ready.py',
        job=smoke['name'],output=smoke['argv'][smoke['argv'].index('--output')+1],
        proposal=str(PROPOSALS[0].relative_to(ROOT)),proposal_sha256=sha(PROPOSALS[0]),
        census5=dict(job=census['name'],proposal=str(PROPOSALS[1].relative_to(ROOT)),proposal_sha256=sha(PROPOSALS[1]),
            output=census['argv'][census['argv'].index('--output')+1],ready=False,conditional=True,
            prerequisite='verify_ready.py recomputes exact current-build d-smoke, clean drain and all 12 real census streams'),
        build_receipt='build-receipt.json',build_receipt_sha256=sha(P/'build-receipt.json'),
        evidence_pins={n:sha(P/n) for n in evidence},shared_rehearsal_warnings=warnings,
        device_executed=False,queued=False,services_started=False,live_queue_written=False,
        require_fresh_live_admission=True,required_empty_queues=['A','B'],require_no_other_inflight=True,
        arithmetic='iq3-p49-split32-v1',kv_dtype='BF16',record_tok_s=30.396,
        output_identity_on_device='pending fresh smoke',diagnostic_only=True,promotable=False,
        views=['S0'],prompts_per_view=12,requested_max_new=64,per_operation_wait_seconds=600,
        first_request_wall_deadline_seconds=None,watchdog_seconds=7200,
        preparation_tests=json.loads((P/'evidence/python-tests.json').read_text())['tests'],
        native_rebuild_scope='none; unchanged binaries; existing wait flag set to 600 seconds',
        reseal_scope='packet58aid sensor dependency and smoke-gated five-view proposal',final_write=True)
    # Last persistent write: every source, proposal, seal, check and note precedes it.
    save(P/'READY-FOR-DEVICE.json',row)
    # Read-only verification includes the newly written marker's own pins.
    for job in jobs: pin_guard.check_job(job)
    print('PASS CPU preparation; smoke ready; census5 conditional on exact fresh d-smoke')

if __name__=='__main__':main()
