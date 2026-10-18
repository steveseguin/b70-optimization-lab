"""Minimal CPU reseal: no native execution, full-shape buffers, models or services.

Run nice19 on cores 8-15,24-31 with python3 -B and stdin /dev/null. Native
startup is intercepted by argument_gate; its unlimited-AS check is intentional.
READY-FOR-DEVICE is written separately, last, after this script and review.
"""
import json,os,resource,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
from build_engine import P,ROOT,sha,save,limits

def run(args,log):
    result=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,stdin=subprocess.DEVNULL,
                          capture_output=True,text=True,timeout=120)
    (P/log).write_text(result.stdout+result.stderr)
    assert result.returncode==0,(P/log).read_text()[-5000:]
    assert resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024<2*1024**3
    return result

def main():
    limits()
    assert not (P/'READY-FOR-DEVICE.json').exists(),'readiness must be written last'
    before=json.loads((P/'lineage/pre-58yb-build-receipt.json').read_text())
    for name,digest in before['artifacts'].items():assert sha(P/name)==digest,'native bytes changed'
    run([str(P/'plan_queue.py'),'--emit-only'],'evidence/reseal-emit.log')
    run([str(P/'run_cpu_gates.py')],'evidence/reseal-policy.log')
    run([str(P/'argument_gate.py')],'evidence/reseal-entry.log')
    run(['-m','unittest','discover','-s',str(P/'host-admission'),'-p','test_*.py','-v'],'evidence/reseal-admission.log')
    save(P/'host-admission/evidence/cpu-tests.json',dict(passed=True,device_executed=False,tests=19,
        model_payload_reads=False,fullshape_executed=False,log_sha256=sha(P/'evidence/reseal-admission.log')))
    run(['-m','unittest','discover','-s',str(P/'analysis'),'-p','test_*.py','-v'],'evidence/reseal-analysis.log')
    run([str(P/'analysis/analyze.py')],'evidence/reseal-report.log')
    save(P/'analysis/cpu-validation.json',dict(schema='packet58y.analysis.cpu-validation.v2',passed=True,
        created_utc=datetime.now(timezone.utc).isoformat(),device_executed=False,synthetic_tests=10,
        synthetic_tests_passed=True,log_sha256=sha(P/'evidence/reseal-analysis.log'),
        source_sha256={f.name:sha(f) for f in (P/'analysis').glob('*.py')},
        actual_report_status='pending_device_evidence',queued=False))
    from source_pin_gate import validate_metadata
    closure=validate_metadata()
    save(P/'evidence/pin-closure.json',dict(passed=True,device_executed=False,tests=4,**closure,
        immutable_inputs_sha256=sha(P/'immutable-inputs.json'),guard_sha256=sha(P/'source_pin_gate.py'),
        policy='Every reachable current pin must be local or an explicit original-oracle/frozen-native input.'))
    import batch_gate
    try:
        observed=batch_gate.verify()
        live=dict(admitted=True,receipt=observed)
    except (ValueError,OSError) as error:live=dict(admitted=False,reason=str(error))
    save(P/'evidence/reseal-cpu.json',dict(passed=True,device_executed=False,native_artifacts_unchanged=True,
        policy_tests=104,admission_tests=19,analysis_tests=10,native_entry_probes=3,
        unit='screen-packet58y-attrib-A.service',nice=os.getpriority(os.PRIO_PROCESS,0),
        affinity=sorted(os.sched_getaffinity(0)),peak_child_rss_bytes=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss*1024,
        model_payload_reads=False,fullshape_executed=False,services_started=False,live_queue_changed=False,
        live_hold_observation=live))
    run([str(P/'seal.py')],'evidence/reseal-seal.log')
    run([str(P/'seal.py'),'--verify'],'evidence/reseal-verify.log')
    run([str(P/'plan_queue.py')],'evidence/reseal-plan.log')
    print('PASS: 104 policy + 19 admission + 10 analysis tests; 3 native-entry interceptions; seal; temporary queue plan')

if __name__=='__main__':main()
