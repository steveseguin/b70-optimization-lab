#!/usr/bin/env python3
"""Experimental capture-ready full12: one same-build measured full-state gate."""
from pathlib import Path
import json
import sys
import finalize_persistent_rolling_suite as frozen
from persistent_rolling_suite_audit import validate_prerequisite_closure,validate_prerequisite_record
from persistent_capture_ready_trace_audit import audit_controller


def capture_plan(plan):
    frozen.need(plan.get('capture_ready_overlap') is True and plan['check_policy']=='measured',
                'explicit measured capture-ready policy required')
    depth=plan.get('speculative_depth',2)
    frozen.need(type(depth)is int and depth in (2,3),'supported speculative depth')
    for stage in plan['stages']:
        argv=stage['argv'];flag='--pipeline-ring-depth'
        frozen.need(argv.count(flag)==int(depth==3),'native depth flag count')
        if depth==3:frozen.need(argv[argv.index(flag)+1]=='3','native depth value')
    provider=plan.get('provider_stage',0)
    frozen.need(type(provider)is int and 0<=provider<len(plan['stages'])-1,'suite capture provider role')
    flag='--pipeline-ring-parent-capture-ack'
    frozen.need([s['argv'].count(flag) for s in plan['stages']]==[int(i==provider) for i in range(len(plan['stages']))],
                'capture-ready provider-owner native flag required')
    for stage in plan['stages']:
        argv=stage['argv'];role_flag='--pipeline-provider-stage'
        frozen.need(argv.count(role_flag)==int(provider>0),'suite exact provider role flag count')
        if provider:frozen.need(argv[argv.index(role_flag)+1]==str(provider),'suite native provider role differs')
    frozen.need(any(p.endswith('/rolling_provider/capture_ready.py') for p in plan['pins']),
                'capture-ready source pin required')


def prerequisite_record(summary,plan_path,policy,qualified_summary_path=None):
    plan=validate_prerequisite_record(summary,plan_path,policy,qualified_summary_path)
    if policy=='measured':
        capture_plan(plan)
        frozen.need(summary.get('capture_ready_overlap') is True and summary['output_tokens']==64
                    and len(summary['request_summaries'])==2
                    and all(r['passed'] is True and r['output_tokens']==32 and r['target_buffer_count']==2065
                            and r['draft_allocation_count']==73 for r in summary['request_summaries']),
                    'same-build gate must include complete capture-ready two32 state parity')
        for field,name in [('capture_ready_finalizer','finalize_persistent_capture_ready_proof.py'),
                           ('capture_ready_auditor','persistent_capture_ready_trace_audit.py')]:
            actual=frozen.identity(Path(__file__).with_name(name));bound=summary[field]
            frozen.need(actual['sha256']==bound['sha256'] and actual['bytes']==bound['bytes'],
                        'capture-ready gate auditor identity differs')
    return plan


def prerequisite_closure(plan,prior,transition=None):
    capture_plan(plan)
    frozen.need(transition is None,'experimental gate requires unchanged execution closure')
    if prior['check_policy']=='qualification':
        # Old qualification supplies comparison provenance, never a new-build gate.
        return None
    capture_plan(prior)
    return validate_prerequisite_closure(plan,prior,None)


def main():
    frozen.validate_prerequisite_record=prerequisite_record
    frozen.validate_prerequisite_closure=prerequisite_closure
    counts=[]
    def tracked_audit(*args,**kwargs):
        replay=audit_controller(*args,**kwargs);counts.append(replay['scheduler_overlap']);return replay
    frozen.audit_controller=tracked_audit
    status=frozen.main()
    out=Path(sys.argv[sys.argv.index('--out')+1]);path=out/'summary.json'
    summary=json.loads(path.read_text())
    comparison,gate=summary['prerequisites']
    frozen.need(comparison['execution_closure'] is None and gate['execution_closure']['passed'] is True,
                'one same-build measured gate required')
    comparison.pop('execution_closure')
    summary['comparison_reference']=dict(comparison,scope='Old accepted full-state comparison provenance; not same-build debug-policy qualification.')
    summary['prerequisites']=[gate]
    summary['scheduler_overlap_by_request']=counts
    summary.update(experimental=True,capture_ready_overlap=True,new_build_debug_policy_qualified=False,
                   capture_ready_finalizer=frozen.identity(Path(__file__)),
                   capture_ready_auditor=frozen.identity(Path(audit_controller.__code__.co_filename)))
    summary['scope']+=' Experimental capture overlap; one same-build measured two32 full-state gate, no new-build debug-policy qualification.'
    frozen.save(path,summary)
    return status


if __name__=='__main__':raise SystemExit(main())
