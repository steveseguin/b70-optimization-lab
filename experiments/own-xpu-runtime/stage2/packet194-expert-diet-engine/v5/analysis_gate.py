"""Analysis gate: real-stream schema positives, missing-stream negatives, the s194 rule on REAL device data (packet189's two
rows - the record line's own k3x views - and packet190's record chain WS128, read where they were retained and pinned here by
sha256), the k3x envelope baseline the diet is measured against, and the diet's price per lever synthesis 4
(+1.32 % per 0.01 ms per GDN layer; packet193's device micro: 10.8 us warm / 15.9 us cold per layer-equivalent).

The map of real inputs (path -> sha256, read where packet186/packet189/packet190 retained them, never copied) is written to
evidence/analysis-real-inputs.json, a receipt outside the lane-queue pin guard's metadata walk (packet187/189's
bracket-gate layout): no device row reads these files, so they are provenance of this CPU gate, not launch pins.
analysis.json carries the map's digest; final_checks.py re-hashes every file of the map."""
import hashlib,json,subprocess,sys,resource
from pathlib import Path
from p194_v5_build_engine import P,LOCAL,ROOT,STAGE,sha,save,limits

EV186=STAGE/'packet186-twocard-v3/v5/evidence'
EV189=STAGE/'packet189-twocard-k3x/v5/evidence'
ROWS189=('device-row0-smoke-k3x-B-p189','device-row1-bracket-v3k-k3x-B-p189')
RUN190=STAGE/'packet190-record-bundle-k3x/build/device-cards01-p190-a/WS128/run'
ORACLE=STAGE/'packet49-integrate/oracle/results'
P193=STAGE/'packet193-expert-diet'
PROMPTS=('incident-retrospective','code-review','customer-email','sql-debugging','release-plan','benchmark-analysis',
         'architecture-tradeoff','bug-report-synthesis','technical-guide','risk-register','performance-hypotheses','decision-memo')
DIET_US=dict(cold=15.9,warm=10.8)   # packet193 device micro (card 2, lanequeue-B39): us saved per layer-equivalent, gate/up kernel


def real_inputs():
    files=[EV189/r/'bracket-summary.json' for r in ROWS189]+[RUN190/'summary.json']
    views=EV189/ROWS189[1]/'run/views'
    for view in ('00-control','01-candidate','02-control','03-candidate','04-control'):
        for prompt in PROMPTS:files+=[views/view/prompt/'receipt.json',views/view/prompt/'rank0/timings.jsonl']
    for d in (EV186/'device-row2-bracket-u-v3-B-p186/run/views/01-candidate/incident64',EV186/'device-row0-smoke-v3-B-p186/run/views/00-candidate/incident64'):
        files+=[f for f in (d/'receipt.json',d/'rank0/timings.jsonl',d/'rank1/timings.jsonl') if f.is_file()]
    for prompt in PROMPTS:files+=[RUN190/'repeat-1'/prompt/'receipt.json',RUN190/'repeat-1'/prompt/'rank1/draft-rows.jsonl',ORACLE/prompt/'result.json']
    files+=[P193/'evidence/diet-B1/window.json',P193/'evidence/diet-B1/samples.jsonl']
    return files


def main():
    limits();tests=[]
    for name in ('test_analyze.py','test_timing_report.py','test_s194_decision.py'):
        cp=subprocess.run([sys.executable,'-B','-m','unittest',name[:-3]],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=1200,cwd=P)
        log=P/'evidence'/('analysis-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0 and '\nOK' in cp.stderr,log.read_text()[-3000:]
        tests.append(dict(name=name,passed=True,log_digest=sha(log)))
    import s194_decision as s
    views=EV189/ROWS189[1]/'run/views'
    k3x=[s.view_stats(views/v,list(PROMPTS),'k3x') for v in ('01-candidate','03-candidate')]
    null=s.gateup_saving([k3x[0],k3x[1],k3x[0]],[k3x[1],k3x[0]])
    record=s.view_stats(RUN190/'repeat-1',list(PROMPTS),'k3x',require_exact=False)
    stored=json.loads((RUN190/'summary.json').read_text())['class_balanced_tok_s_1_100_intervals_after_ttft']['median']
    assert stored==s.RECORD and abs(s.RECORD_BAR-63.592)<5e-4
    price={k:dict(us_per_layer=v,gain_percent=s.PRICE_PCT_PER_MS_PER_GDN_LAYER*v/1000.0) for k,v in DIET_US.items()}
    assert null['min_both_ranks_us_per_layer'] is not None and abs(null['min_both_ranks_us_per_layer'])<1.0
    pins={str(f.relative_to(ROOT)):sha(f) for f in real_inputs()}
    inputs=P/'evidence/analysis-real-inputs.json'
    save(inputs,dict(schema='packet194.analysis-real-inputs.v1',device_executed=False,read_in_place=True,files=pins))
    digest=hashlib.sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'analysis_gate.py',P/'analyze.py',P/'timing_report.py',P/'test_analyze.py',P/'test_timing_report.py',
             P/'s194_decision.py',P/'interval_model.py',P/'test_s194_decision.py']}
    save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,real_historical_schema_checked=True,missing_streams_and_scopes_refused=True,
        head_scope_absence_enforced=True,boundary_scopes_mandatory_every_cycle=True,staged_view_refuses_synchronous_token_history=True,first_request_gate_in_every_row=True,
        elapsed_time_informational_only=True,draft_definition='D = draft_rows.draft_wall_ms (publication observed), never the op-9 command duration',
        s194_rule_on_real_packet189=('NOT A SCREEN WINNER on packet189\'s own k3x views as both control and candidate (null: gain -0.03 %, drift 0.03 %, per-layer saving ~0 us -> the saving '
                                     'kill rule fires); the record-line V3 views as candidate are not a winner either; scalings of the real k3x views with an injected '
                                     '12 us/layer saving cover chain (+2.5 %, +2.2 %), winner-only (+2.15 % below the record bar, +1.5 %), below +0.5 %, drift > 0.5 %, inexact, '
                                     'proposals, acceptance, a 3 us saving, an unmeasured saving, a missing smoke and a wrong variant'),
        s194_null_saving_on_real_packet189=null,
        s194_view_stats_on_real_packet190=dict(hits=record['hits'],misses=record['misses'],hit_ms=record['hit']['elapsed'],miss_ms=record['miss']['elapsed'],
                                               boundary_ms=record['hit']['Bd'],draft_wall_ms=record['hit']['D'],draft_op9_ms=record['hit']['D_op9'],
                                               boundary_over_draft=record['hit']['boundary_over_draft'],rank1_binds=record['hit']['rank1_binds_emission'],
                                               hit_A_ms=record['hit']['A'],hit_B_ms=record['hit']['B']),
        record=dict(value=s.RECORD,source=str((RUN190/'summary.json').relative_to(ROOT)),chain_bar=s.RECORD_BAR,screen_bar_percent=0.5,chain_bar_percent=2.0),
        diet_price=dict(rule='+1.32 % per 0.01 ms per GDN layer on both ranks (lever synthesis 4, packet190 analysis/lever-synthesis-4-20261022.md)',
                        packet193_device_micro=dict(gateup_cold_us=dict(production=73.85,diet=57.92,ratio=0.784),gateup_warm_us=dict(production=46.77,diet=36.1,ratio=0.771),
                                                    source='packet193-expert-diet/evidence/diet-B1/samples.jsonl (medians computed by the coordinator; the packet\'s analyzer did not run)'),
                        projected=price,kill_rule_us_per_layer=s.SAVING_MIN_US,chain_rule_needs_us_per_layer=15.1,screen_bar_needs_us_per_layer=3.8,
                        caveat='the in-engine regime sits between the cold and warm strata; the host-side per-layer saving of the screen decides, the micro only prices'),
        k3x_record_line_envelope_baseline=dict(source='packet189 row-1 k3x views 01/03 (the record line\'s own engine path), decode cycles, p150 host scopes',
                                               half_total_ms=sum(x['envelope']['scopes_ms']['half_total'] for x in k3x)/2,layer_body_ms=sum(x['envelope']['scopes_ms']['layer_body'] for x in k3x)/2,
                                               boundary_body_ms=sum(x['envelope']['scopes_ms']['boundary_body'] for x in k3x)/2,boundary_export_ms=sum(x['envelope']['boundary_export_ms'] for x in k3x)/2,
                                               hit_A_ms=sum(x['hit']['A'] for x in k3x)/2,hit_B_ms=sum(x['hit']['B'] for x in k3x)/2,hit_Bd_ms=sum(x['hit']['Bd'] for x in k3x)/2,hit_draft_wall_ms=sum(x['hit']['D'] for x in k3x)/2,
                                               hit_elapsed_ms=sum(x['hit']['elapsed'] for x in k3x)/2,miss_elapsed_ms=sum(x['miss']['elapsed'] for x in k3x)/2),
        real_inputs_read_in_place=len(pins),real_inputs_receipt=str(inputs.relative_to(ROOT)),real_inputs_map_sha256=digest,
        tests=tests,sources=sources))
    print('analysis gate PASS: real inputs pinned in place',len(pins),'map',digest[:16])


if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000));main()
