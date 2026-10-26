#!/usr/bin/env python3
"""Experimental full12 copy/placement screen; no same-build short-gate certification."""
from pathlib import Path
import json
import sys
import finalize_persistent_rolling_suite as frozen
from persistent_capture_ready_trace_audit import audit_controller


def comparison_only(plan,prior,transition=None):
    frozen.need(plan.get('capture_ready_overlap') is True,'explicit capture-ready screen required')
    provider=plan.get('provider_stage',0)
    frozen.need(type(provider)is int and 0<=provider<len(plan['stages'])-1,'screen nonfinal provider role')
    for flag in ('--pipeline-ring-recursive-flat-copy','--pipeline-ring-parent-capture-ack'):
        frozen.need([s['argv'].count(flag) for s in plan['stages']]==[int(i==provider) for i in range(len(plan['stages']))],
                    'screen candidate flag must belong only to provider owner: '+flag)
    frozen.need(transition is None,'screen does not consume a planner-transition qualification')
    return None


def main():
    frozen.validate_prerequisite_closure=comparison_only
    counts=[]
    def replay(*args,**kwargs):
        result=audit_controller(*args,**kwargs);counts.append(result['scheduler_overlap']);return result
    frozen.audit_controller=replay
    status=frozen.main()
    out=Path(sys.argv[sys.argv.index('--out')+1]);path=out/'summary.json'
    summary=json.loads(path.read_text());refs=summary.pop('prerequisites')
    for ref in refs:ref.pop('execution_closure')
    summary.update(comparison_references=refs,screening_only=True,same_build_short_gate=False,
        certified=False,speed_claim=False,experimental=True,scheduler_overlap_by_request=counts,
        screening_finalizer=frozen.identity(Path(__file__)),
        capture_ready_auditor=frozen.identity(Path(audit_controller.__code__.co_filename)))
    summary['scope']+=' Copy/placement experimental screen; prior proofs are comparison provenance, not same-build qualification. Extra draft-state gate remains pending.'
    frozen.save(path,summary)
    (out/'RESULT.md').write_text('# Experimental copy/placement screen\n\nExact twelve-request outputs and final target state passed; no same-build short gate or draft-state qualification is claimed. [Summary](summary.json).\n')
    return status


if __name__=='__main__':raise SystemExit(main())
