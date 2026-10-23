"""Analysis gate (packet191): real-stream schema positives, missing-stream negatives, and the s191 report on REAL device data:
packet189's two measured k3x views (row 1, the off/record path) and packet190's record chain WS128 (read where they were
retained and pinned here by sha256), the engine's own CPU format proof of the site rows (full-shape.json sites_format, written
by the real attribution_row on the real production plan), and synthetic instrumented views built on packet189's real receipts
with packet110's call times (the report must reproduce packet110's class table, flag the excess-eligible classes, name their
closures and say no open mechanism remains; every kill rule has a positive and a negative).

The map of real inputs (path -> sha256, read in place, never copied) is written to evidence/analysis-real-inputs.json, outside
the lane-queue pin guard's metadata walk (packet187/188/189's bracket-gate layout): no device row reads these files, so they are
provenance of this CPU gate, not launch pins. analysis.json carries the map's digest; final_checks.py re-hashes every file."""
import json,subprocess,sys,resource,hashlib
from pathlib import Path
from p191_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

STAGE=LOCAL.parent
EV186=STAGE/'packet186-twocard-v3/v5/evidence'
EV189=STAGE/'packet189-twocard-k3x/v5/evidence'
ROWS189=('device-row0-smoke-k3x-B-p189','device-row1-bracket-v3k-k3x-B-p189')
RUN190=STAGE/'packet190-record-bundle-k3x/build/device-cards01-p190-a/WS128/run/repeat-1'
SUM190=STAGE/'packet190-record-bundle-k3x/evidence/device-cards01-p190-a/WS128/run/summary.json'
ORACLE=STAGE/'packet49-integrate/oracle/results'
PROMPTS=('incident-retrospective','code-review','customer-email','sql-debugging','release-plan','benchmark-analysis',
         'architecture-tradeoff','bug-report-synthesis','technical-guide','risk-register','performance-hypotheses','decision-memo')


def real_inputs():
    import s191_report as s
    files=[EV189/r/'bracket-summary.json' for r in ROWS189]+[SUM190,ROOT/s.P110['path'],ROOT/s.P77_BYTES['path'],ROOT/s.P72_CENSUS['path']]
    views=EV189/ROWS189[1]/'run/views'
    for view in ('01-candidate','03-candidate'):
        for prompt in PROMPTS:files+=[views/view/prompt/'receipt.json',views/view/prompt/'rank0/timings.jsonl',views/view/prompt/'rank1/timings.jsonl',views/view/prompt/'rank1/draft-rows.jsonl']
    for prompt in PROMPTS:files+=[RUN190/prompt/'receipt.json',ORACLE/prompt/'result.json']
    # test_analyze.py fixtures: packet186's real V3 incident64 streams (unchanged since packet188/189)
    for d in (EV186/'device-row2-bracket-u-v3-B-p186/run/views/01-candidate/incident64',EV186/'device-row0-smoke-v3-B-p186/run/views/00-candidate/incident64'):
        files+=[f for f in (d/'receipt.json',d/'rank0/timings.jsonl',d/'rank1/timings.jsonl') if f.is_file()]
    # packet189's retained production-shape archives of the k3x-first load (the launch label census the synthetic views use)
    import test_s191_report as t
    files+=[t.P189_SHAPE[0],t.P189_SHAPE[1]]
    return files


def main():
    limits();tests=[]
    for name in ('test_analyze.py','test_timing_report.py','test_s191_report.py'):
        cp=subprocess.run([sys.executable,'-B','-m','unittest',name[:-3]],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=1800,cwd=P)
        log=P/'evidence'/('analysis-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0 and '\nOK' in cp.stderr,log.read_text()[-3000:]
        tests.append(dict(name=name,passed=True,log_digest=sha(log)))
    import s191_report as s,test_s191_report as t
    views=EV189/ROWS189[1]/'run/views'
    off=[s.view_stats(views/v,list(PROMPTS),'k3x-off') for v in ('01-candidate','03-candidate')]
    record=s.view_stats(RUN190,list(PROMPTS),'k3x-off',require_exact=False)
    p189=s.packet189_k3x_reference();p190=s.packet190_record_reference()
    shape=json.loads((P/'evidence/full-shape.json').read_text());fmt=shape['sites_format']
    # The synthetic instrumented views (packet189's real receipts/timing streams + packet110 call times) through the real report path.
    on_a,_=t.synthetic_on_view('gate-on-a',views/'01-candidate');on_b,_=t.synthetic_on_view('gate-on-b',views/'03-candidate')
    report=s.decide(t.SMOKE,t.bracket_from_packet189([on_a,on_b]))
    withheld=s.decide(t.SMOKE,t.bracket_from_packet189([on_a,on_b],on_scale=0.92))
    import test_s191_report as tt
    if tt._SCRATCH is not None:tt._SCRATCH.cleanup();tt._SCRATCH=None
    assert report['measurement_complete'] and report['kill_rules']['fired']==[] and not withheld['table_admissible'] and withheld['class_table']=={}
    a=report['class_table']['rank0/speculative'];b=report['class_table']['rank1/half']
    pins={str(f.relative_to(ROOT)):sha(f) for f in real_inputs()}
    inputs=P/'evidence/analysis-real-inputs.json'
    save(inputs,dict(schema='packet191.analysis-real-inputs.v1',device_executed=False,read_in_place=True,files=pins))
    digest=hashlib.sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    analysis=sorted((LOCAL/'analysis').rglob('*'))
    sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'analysis_gate.py',P/'analyze.py',P/'timing_report.py',P/'test_analyze.py',P/'test_timing_report.py',
             P/'s191_report.py',P/'interval_model.py',P/'test_s191_report.py',*[f for f in analysis if f.is_file()]]}
    save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,real_historical_schema_checked=True,missing_streams_and_scopes_refused=True,
        head_scope_absence_enforced=True,boundary_scopes_mandatory_every_cycle=True,staged_view_refuses_synchronous_token_history=True,first_request_gate_in_every_row=True,
        elapsed_time_informational_only=True,draft_definition='D = draft_rows.draft_wall_ms (publication observed), never the op-9 command duration',
        s191_rule=s.RULE,
        off_views_on_real_packet189=dict(rates=p189['rates'],source=p189['source'],sha256=p189['sha256'],
            hit_ms=[v['hit']['elapsed'] for v in off],miss_ms=[v['miss']['elapsed'] for v in off],layer_body_ms=[v['envelope']['scopes_ms']['layer_body'] for v in off],
            boundary_ms=[v['hit']['Bd'] for v in off],draft_wall_ms=[v['hit']['D'] for v in off],site_rows=0),
        record_on_real_packet190=dict(rate=p190['rate'],source=p190['source'],sha256=p190['sha256'],hits=record['hits'],misses=record['misses'],
            hit_ms=record['hit']['elapsed'],miss_ms=record['miss']['elapsed']),
        engine_site_row_format_proof=fmt,
        s191_on_synthetic_instrumented_views=dict(outcome=report['outcome'],instrumented_over_control=report['instrumented_over_control'],
            control_drift_percent=report['control_drift_percent'],off_timing_equivalent_to_packet189=report['off_timing_equivalent_to_packet189'],
            completeness=report['kill_rules']['completeness'],chain_eligible_by_excess=report['chain_eligible_by_excess'],screen_eligible_by_excess=report['screen_eligible_by_excess'],
            open_mechanisms_remaining=report['open_mechanisms_remaining'],
            rank0_speculative_us_per_gdn_layer={g:a[g]['us_per_gdn_layer'] for g in a if a[g]['us_per_gdn_layer'] is not None},
            rank0_speculative_excess_floor_us_per_gdn_layer={g:a[g]['excess_floor_us_per_gdn_layer'] for g in a if a[g]['excess_floor_us_per_gdn_layer'] is not None},
            rank1_half_us_per_gdn_layer={g:b[g]['us_per_gdn_layer'] for g in b if b[g]['us_per_gdn_layer'] is not None},
            rank0_excess_over_packet110_us_per_gdn_layer={g:a[g]['excess_packet110_us_per_gdn_layer'] for g in a if a[g]['excess_packet110_us_per_gdn_layer'] is not None},
            note='synthetic durations = packet110 call times on the real plan labels and the real packet189 streams: the table must reproduce packet110 (excess over packet110 ~ 0); this is a packaging test, not a measurement'),
        overhead_withheld=dict(outcome=withheld['outcome'],instrumented_over_control=withheld['instrumented_over_control'],class_table_withheld=withheld['class_table']=={}),
        real_inputs_read_in_place=len(pins),real_inputs_receipt=str(inputs.relative_to(ROOT)),real_inputs_map_sha256=digest,
        tests=tests,sources=sources))
    print('analysis gate PASS: real inputs pinned in place',len(pins),'map',digest[:16],'| synthetic report:',report['outcome'][:120])


if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000));main()
