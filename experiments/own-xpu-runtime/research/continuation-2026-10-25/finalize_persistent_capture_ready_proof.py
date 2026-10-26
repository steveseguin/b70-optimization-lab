#!/usr/bin/env python3
"""Explicit capture-ready entrypoint reusing persistent full-state qualification."""
import finalize_persistent_rolling_proof as frozen
from persistent_capture_ready_trace_audit import audit_controller
from pathlib import Path

original_validate=frozen.validate_identity

def validate(plan,suite,terminal,reference):
    frozen.need(plan.get('capture_ready_overlap') is True,'explicit capture-ready true required')
    provider=plan.get('provider_stage',0)
    frozen.need(type(provider)is int and 0<=provider<len(plan['stages'])-1,'capture provider role')
    flag='--pipeline-ring-parent-capture-ack'
    frozen.need([s['argv'].count(flag) for s in plan['stages']]==[int(i==provider) for i in range(len(plan['stages']))],
                'capture-ready native opt-in only on provider owner')
    frozen.need(any(p.endswith('/rolling_provider/capture_ready.py') for p in plan['pins']),
                'capture-ready transport source pin required')
    for stage in plan['stages']:
        argv=stage['argv'];role_flag='--pipeline-provider-stage'
        frozen.need(argv.count(role_flag)==int(provider>0),'exact native provider role flag count')
        if provider:frozen.need(argv[argv.index(role_flag)+1]==str(provider),'native provider role differs')
    return original_validate(plan,suite,terminal,reference)

if __name__=='__main__':
    frozen.validate_identity=validate
    counts=[]
    def tracked_audit(*args,**kwargs):
        replay=audit_controller(*args,**kwargs);counts.append(replay['scheduler_overlap']);return replay
    frozen.audit_controller=tracked_audit
    # The reused finalizer retains its own identity; add the narrow extension's identities.
    status=frozen.main()
    import sys,json
    out=Path(sys.argv[sys.argv.index('--out')+1])
    path=out/'summary.json';summary=json.loads(path.read_text())
    summary['capture_ready_overlap']=True
    summary['scheduler_overlap_by_request']=counts
    summary['capture_ready_finalizer']=frozen.identity(Path(__file__))
    summary['capture_ready_auditor']=frozen.identity(Path(audit_controller.__code__.co_filename))
    frozen.save(path,summary)
    raise SystemExit(status)
