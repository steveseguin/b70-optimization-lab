"""Fail-closed packet86 scope. Even production control is never a promotion view."""
import copy
import json
from pathlib import Path
P=Path(__file__).resolve().parent
VIEWS=('production','exp-nodeq','exp-constgrid','exp-onecached','hc-nodeq','hc-constscale','exp-loadkeep','hc-loadkeep')
NONEXACT=set(VIEWS)-{'production','exp-loadkeep','hc-loadkeep'}

def guard(view, purpose='screen', timing='attribution'):
    if view not in VIEWS or purpose!='screen' or timing!='attribution':
        raise ValueError('packet86 diagnostic-only: bundle, chain, submission and headline paths forbidden')

def selection(view):
    guard(view)
    row=json.loads((P/'selection.json').read_text())
    if view.startswith('exp-'):row['choices']['experts']=view
    if view.startswith('hc-'):row['choices']['hc_gate']=view
    return row

def labels(view):
    guard(view)
    return dict(diagnostic_nonexact=True, view=view, output_changed_by_design=view in NONEXACT,
                qualifying=False, submission_eligible=False, speed_evidence_eligible=False,
                byte_identity_required=view not in NONEXACT,
                realistic_final_gate={'passed':False,'reason':'packet86 non-exact limiter diagnostic; never a bundle/chain/headline'})

def classify(view, tokens, expected, count):
    guard(view)
    # Shape/protocol errors are NOT output mismatches and remain fatal.
    if len(tokens)!=count or len(expected)<count:
        raise ValueError('diagnostic request length/protocol failure')
    exact=tokens==expected[:count]
    if view not in NONEXACT and not exact:
        raise ValueError('production/load-retention control every-token mismatch')
    return dict(exact_oracle=exact, outcome='diagnostic_output_mismatch' if not exact else 'observed_match',
                oracle_check={'passed':exact,'every_emitted_token':True,'expected_mismatch':view in NONEXACT})
