"""Analysis gate: real-stream schema positives, missing-stream negatives, the s188 rule on REAL device data (packet186's
rows and packet187's record chain, read where they were retained and pinned here by sha256), the record-line envelope
baseline the trims are measured against, and the lever-synthesis replay the composite was priced with (analysis/).

The map of real inputs (path -> sha256, read where packet186/packet187 retained them, never copied) is written to
evidence/analysis-real-inputs.json, a receipt outside the lane-queue pin guard's metadata walk (packet187's
bracket-gate layout): no device row reads these files, so they are provenance of this CPU gate, not launch pins.
analysis.json carries the map's digest; final_checks.py re-hashes every file of the map."""
import json,subprocess,sys,resource
from pathlib import Path
from p188_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

STAGE=LOCAL.parent
EV186=STAGE/'packet186-twocard-v3/v5/evidence'
RUN187=STAGE/'packet187-record-bundle-v3/build/device-cards01-p187-a/WS128/run/repeat-1'
SUM187=STAGE/'packet187-record-bundle-v3/evidence/device-cards01-p187-a/WS128/summary.json'
ORACLE=STAGE/'packet49-integrate/oracle/results'
PROMPTS=('incident-retrospective','code-review','customer-email','sql-debugging','release-plan','benchmark-analysis',
         'architecture-tradeoff','bug-report-synthesis','technical-guide','risk-register','performance-hypotheses','decision-memo')


def real_inputs():
    b=EV186/'device-row2-bracket-u-v3-B-p186';views=b/'run/views'
    files=[b/'bracket-summary.json',EV186/'device-row0-smoke-v3-B-p186/bracket-summary.json',SUM187]
    for view in ('01-candidate','03-candidate'):
        for prompt in PROMPTS:files+=[views/view/prompt/'receipt.json',views/view/prompt/'rank0/timings.jsonl']
    for d in (views/'01-candidate/incident64',EV186/'device-row0-smoke-v3-B-p186/run/views/00-candidate/incident64'):
        files+=[f for f in (d/'receipt.json',d/'rank0/timings.jsonl',d/'rank1/timings.jsonl') if f.is_file()]
    for prompt in PROMPTS:files+=[RUN187/prompt/'receipt.json',RUN187/prompt/'rank1/draft-rows.jsonl',ORACLE/prompt/'result.json']
    return files


def main():
    limits();tests=[]
    for name in ('test_analyze.py','test_timing_report.py','test_s188_decision.py'):
        cp=subprocess.run([sys.executable,'-B','-m','unittest',name[:-3]],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900,cwd=P)
        log=P/'evidence'/('analysis-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0 and '\nOK' in cp.stderr,log.read_text()[-3000:]
        tests.append(dict(name=name,passed=True,log_digest=sha(log)))
    import s188_decision as s
    views=EV186/'device-row2-bracket-u-v3-B-p186/run/views'
    baseline=[s.view_stats(views/v,list(PROMPTS),'v3') for v in ('01-candidate','03-candidate')]
    env=lambda k:sum(b['envelope'][k] for b in baseline)/2
    parts=lambda k:sum(b['envelope']['envelope_parts_ms'][k] for b in baseline)/2
    record=s.view_stats(RUN187,list(PROMPTS),'v3',require_exact=False)
    analysis=sorted((LOCAL/'analysis').rglob('*'))
    pins={str(f.relative_to(ROOT)):sha(f) for f in real_inputs()}
    inputs=P/'evidence/analysis-real-inputs.json'
    save(inputs,dict(schema='packet188.analysis-real-inputs.v1',device_executed=False,read_in_place=True,files=pins))
    digest=__import__('hashlib').sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'analysis_gate.py',P/'analyze.py',P/'timing_report.py',P/'test_analyze.py',P/'test_timing_report.py',
             P/'s188_decision.py',P/'interval_model.py',P/'test_s188_decision.py',*[f for f in analysis if f.is_file()]]}
    save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,real_historical_schema_checked=True,missing_streams_and_scopes_refused=True,
        head_scope_absence_enforced=True,boundary_scopes_mandatory_every_cycle=True,staged_view_refuses_synchronous_token_history=True,first_request_gate_in_every_row=True,
        elapsed_time_informational_only=True,
        s188_rule_on_real_packet186=('NOT A WINNER with a k3 equal to the real V3 views (every kill rule but the draft window fires); real V3 over real U '
                                     '(+4.66 %) is a screen winner but NOT a chain (60.533 < 61.873); scalings cover chain, winner-only, below +0.5 %, drift, inexact, proposals, missing smoke'),
        s188_view_stats_on_real_packet187=dict(hits=record['hits'],misses=record['misses'],hit_ms=record['hit']['elapsed'],miss_ms=record['miss']['elapsed'],
                                               boundary_ms=record['hit']['Bd'],boundary_over_draft=record['hit']['boundary_over_draft'],rank1_binds=record['hit']['rank1_binds_emission']),
        record_line_envelope_baseline=dict(source='packet186 V3 views 01/03 (the record-line engine path), decode cycles, p150 host scopes',
                                           half_total_ms=sum(b['envelope']['scopes_ms']['half_total'] for b in baseline)/2,
                                           layer_body_ms=sum(b['envelope']['scopes_ms']['layer_body'] for b in baseline)/2,
                                           rank0_half_envelope_ms=env('rank0_half_envelope_ms'),snapshot_ms=parts('snapshot'),token_history_ms=parts('token_history'),
                                           token_prep_ms=parts('token_prep'),unattributed_ms=env('envelope_unattributed_ms'),
                                           p76_retirement_ms_per_half=env('p76_retirement_ms_per_half'),prepare_ms_per_half=env('prepare_ms_per_half'),
                                           boundary_envelope_ms=env('boundary_envelope_ms'),boundary_export_ms=env('boundary_export_ms'),
                                           hit_A_ms=sum(b['hit']['A'] for b in baseline)/2,hit_Bd_ms=sum(b['hit']['Bd'] for b in baseline)/2),
        real_inputs_read_in_place=len(pins),real_inputs_receipt=str(inputs.relative_to(ROOT)),real_inputs_map_sha256=digest,
        tests=tests,sources=sources))
    print('analysis gate PASS: real inputs pinned in place',len(pins),'map',digest[:16])


if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000));main()
