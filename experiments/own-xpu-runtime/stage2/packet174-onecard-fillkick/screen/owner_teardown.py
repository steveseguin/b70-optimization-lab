"""Prove the one-card owner drained before fallible Python result reporting."""
import json
from teardown_on_error import finish_on_error, require_reaped, require, VERSION

def finish_model_owner(child, output, admission, check):
    def prove():
        require(child is not None and child.poll() is not None,'native driver still live')
        require_reaped([child.pid,*map(int,admission.owners)],admission.proc)
        check()  # Caller's fault cursor includes the complete supervisor postflight.
        proof=json.loads((output/'run/run/receipt.json').read_text())
        require(proof.get('safe_to_exit') is True and proof.get('device_executed') is True
                and proof.get('owner_cards')==1,'native teardown missing')
        owners=proof.get('teardown',[])
        require(len(owners)==1,'one native teardown required')
        owner=owners[0]
        require(owner.get('status')=='complete' and owner.get('safe_to_exit') is True
                and owner.get('idle_marker_complete') is True and not owner.get('error')
                and all(type(owner.get(k)) is int and owner[k]==0 for k in ('exit_code','live_bytes','in_flight')),
                'native owner did not drain')
    error=RuntimeError('screen reporting or native failure')
    passed=finish_on_error(error,prove=prove,complete=admission.devices_drained)
    require(passed,str(error)+str(getattr(error,'__notes__',[])))
    return dict(passed=True,helper=VERSION,experiment_passed=False)
