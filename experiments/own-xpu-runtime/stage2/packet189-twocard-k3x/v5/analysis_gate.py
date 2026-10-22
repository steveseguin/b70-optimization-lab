"""Analysis gate: real-stream schema positives, missing-stream negatives, the s189 rule on REAL device data (packet188's three
rows and packet187's record chain, read where they were retained and pinned here by sha256), the record-line envelope
baseline (packet188's in-load V3 views) the trims are measured against, the pinned fresh V3 reference (packet188 row 1),
and the lever-synthesis-3 replay the k3x packet was priced with (analysis/replay_k3x.py: record 60.65951991975228 and
+2.74 % for k3x).

The map of real inputs (path -> sha256, read where packet186/packet188/packet187 retained them, never copied) is written to
evidence/analysis-real-inputs.json, a receipt outside the lane-queue pin guard's metadata walk (packet187's
bracket-gate layout): no device row reads these files, so they are provenance of this CPU gate, not launch pins.
analysis.json carries the map's digest; final_checks.py re-hashes every file of the map."""
import json,subprocess,sys,resource
from pathlib import Path
from p189_v5_build_engine import P,LOCAL,ROOT,sha,save,limits

STAGE=LOCAL.parent
EV186=STAGE/'packet186-twocard-v3/v5/evidence'
EV188=STAGE/'packet188-twocard-k3-composite/v5/evidence'
ROWS188=('device-row0-smoke-k3trims-B-p188','device-row1-control-v3-B-p188','device-row2-bracket-v3k-k3trims-B-p188')
RUN187=STAGE/'packet187-record-bundle-v3/build/device-cards01-p187-a/WS128/run/repeat-1'
SUM187=STAGE/'packet187-record-bundle-v3/evidence/device-cards01-p187-a/WS128/summary.json'
ORACLE=STAGE/'packet49-integrate/oracle/results'
PROMPTS=('incident-retrospective','code-review','customer-email','sql-debugging','release-plan','benchmark-analysis',
         'architecture-tradeoff','bug-report-synthesis','technical-guide','risk-register','performance-hypotheses','decision-memo')


def real_inputs():
    files=[EV188/r/'bracket-summary.json' for r in ROWS188]+[SUM187]
    views=EV188/ROWS188[2]/'run/views'
    for view in ('00-control','01-candidate','02-control','03-candidate','04-control'):
        for prompt in PROMPTS:files+=[views/view/prompt/'receipt.json',views/view/prompt/'rank0/timings.jsonl']
    for prompt in PROMPTS:files+=[EV188/ROWS188[1]/'run/views/00-control'/prompt/'receipt.json',EV188/ROWS188[1]/'run/views/00-control'/prompt/'rank0/timings.jsonl']
    # test_analyze.py fixtures: packet186's real V3 incident64 streams (unchanged since packet188)
    for d in (EV186/'device-row2-bracket-u-v3-B-p186/run/views/01-candidate/incident64',EV186/'device-row0-smoke-v3-B-p186/run/views/00-candidate/incident64'):
        files+=[f for f in (d/'receipt.json',d/'rank0/timings.jsonl',d/'rank1/timings.jsonl') if f.is_file()]
    for prompt in PROMPTS:files+=[RUN187/prompt/'receipt.json',RUN187/prompt/'rank1/draft-rows.jsonl',ORACLE/prompt/'result.json']
    return files


def main():
    limits();tests=[]
    for name in ('test_analyze.py','test_timing_report.py','test_s189_decision.py'):  # s189 on real packet188/187 data + the synthesis-3 replay
        cp=subprocess.run([sys.executable,'-B','-m','unittest',name[:-3]],stdin=subprocess.DEVNULL,capture_output=True,text=True,timeout=900,cwd=P)
        log=P/'evidence'/('analysis-'+name+'.log');log.write_text(cp.stdout+cp.stderr);assert cp.returncode==0 and '\nOK' in cp.stderr,log.read_text()[-3000:]
        tests.append(dict(name=name,passed=True,log_digest=sha(log)))
    import s189_decision as s
    views=EV188/ROWS188[2]/'run/views'
    baseline=[s.view_stats(views/v,list(PROMPTS),'v3k') for v in ('00-control','02-control','04-control')]
    measured=[s.view_stats(views/v,list(PROMPTS),'k3x') for v in ('01-candidate','03-candidate')]
    env=lambda k:sum(b['envelope'][k] for b in baseline)/3
    parts=lambda k:sum(b['envelope']['envelope_parts_ms'][k] for b in baseline)/3
    record=s.view_stats(RUN187,list(PROMPTS),'v3',require_exact=False)
    fresh=s.fresh_v3_record()
    kills=s.kill_rules(baseline,measured)
    spec=__import__('importlib.util').util.spec_from_file_location('replay_k3x',LOCAL/'analysis/replay_k3x.py');m=__import__('importlib.util').util.module_from_spec(spec);spec.loader.exec_module(m)
    out,w=m.compute();central=next(p for p in w['P'] if p['label'].startswith('k3x: k3 + trims, boundary export on the copy engine (central)'))
    pessimistic=next(p for p in w['P'] if p['label'].startswith('k3x: everything pessimistic'));optimistic=next(p for p in w['P'] if p['label'].startswith('k3x: everything optimistic'))
    assert abs(w['base']-s.RECORD)<1e-9 and central['rate']>s.RECORD_BAR and pessimistic['rate']>s.RECORD_BAR
    analysis=sorted((LOCAL/'analysis').rglob('*'))
    pins={str(f.relative_to(ROOT)):sha(f) for f in real_inputs()}
    inputs=P/'evidence/analysis-real-inputs.json'
    save(inputs,dict(schema='packet189.analysis-real-inputs.v1',device_executed=False,read_in_place=True,files=pins))
    digest=__import__('hashlib').sha256(json.dumps(pins,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    sources={str(f.relative_to(ROOT)):sha(f) for f in [P/'analysis_gate.py',P/'analyze.py',P/'timing_report.py',P/'test_analyze.py',P/'test_timing_report.py',
             P/'s189_decision.py',P/'interval_model.py',P/'test_s189_decision.py',*[f for f in analysis if f.is_file()]]}
    save(P/'evidence/analysis.json',dict(passed=True,device_executed=False,real_historical_schema_checked=True,missing_streams_and_scopes_refused=True,
        head_scope_absence_enforced=True,boundary_scopes_mandatory_every_cycle=True,staged_view_refuses_synchronous_token_history=True,first_request_gate_in_every_row=True,
        elapsed_time_informational_only=True,draft_definition='D = draft_rows.draft_wall_ms (publication observed), never the op-9 command duration',
        s189_rule_on_real_packet188=('NOT A SCREEN WINNER on packet188\'s measured k3+trims views relabeled k3x (-0.26 %; export 0.592 ms, boundary 2.005 ms, hit saving 0.071 ms and '
                                     'boundary > draft wall on 100 % of hits fire; the trims rule passes at 0.142 ms); a null k3x (V3 views as candidate) is not a winner; '
                                     'scalings cover chain, winner-only (incl. +2.1 % below the record bar), below +0.5 %, drift, inexact, proposals, missing smoke, wrong variant'),
        s189_kill_rules_on_real_packet188=kills,
        fresh_v3_reference=dict(source=fresh['source'],sha256=fresh['sha256'],rate=fresh['rate'],read_in_place=True),
        s189_view_stats_on_real_packet187=dict(hits=record['hits'],misses=record['misses'],hit_ms=record['hit']['elapsed'],miss_ms=record['miss']['elapsed'],
                                               boundary_ms=record['hit']['Bd'],draft_wall_ms=record['hit']['D'],draft_op9_ms=record['hit']['D_op9'],boundary_over_draft=record['hit']['boundary_over_draft'],rank1_binds=record['hit']['rank1_binds_emission']),
        lever_synthesis_3_replay=dict(record_replay=w['base'],record=s.RECORD,inload_v3=w['v3_rates'],measured_k3trims=w['k3_rates'],
                                      k3x_central=dict(rate=central['rate'],gain_pct=central['gain_pct'],hit_ms=central['hit_ms'],miss_ms=central['miss_ms']),
                                      k3x_pessimistic=dict(rate=pessimistic['rate'],gain_pct=pessimistic['gain_pct']),k3x_optimistic=dict(rate=optimistic['rate'],gain_pct=optimistic['gain_pct']),
                                      chain_bar=s.RECORD_BAR,layer26_body_ms=w['A']['body']['d_hit'],export_kio_minus_copy_ms=w['A']['export']['d_hit'],
                                      export_ns_per_byte=dict(copy=w['A']['export_ns_per_byte_v3'],kio=w['A']['export_ns_per_byte_k3trims'])),
        record_line_envelope_baseline=dict(source='packet188 in-load V3 views 00/02/04 of the k3 storage (the record-line engine path), decode cycles, p150 host scopes',
                                           half_total_ms=sum(b['envelope']['scopes_ms']['half_total'] for b in baseline)/3,
                                           layer_body_ms=sum(b['envelope']['scopes_ms']['layer_body'] for b in baseline)/3,
                                           rank0_half_envelope_ms=env('rank0_half_envelope_ms'),snapshot_ms=parts('snapshot'),token_history_ms=parts('token_history'),
                                           token_prep_ms=parts('token_prep'),unattributed_ms=env('envelope_unattributed_ms'),
                                           p76_retirement_ms_per_half=env('p76_retirement_ms_per_half'),prepare_ms_per_half=env('prepare_ms_per_half'),
                                           boundary_envelope_ms=env('boundary_envelope_ms'),boundary_export_ms=env('boundary_export_ms'),
                                           hit_A_ms=sum(b['hit']['A'] for b in baseline)/3,hit_Bd_ms=sum(b['hit']['Bd'] for b in baseline)/3,hit_draft_wall_ms=sum(b['hit']['D'] for b in baseline)/3),
        real_inputs_read_in_place=len(pins),real_inputs_receipt=str(inputs.relative_to(ROOT)),real_inputs_map_sha256=digest,
        tests=tests,sources=sources))
    print('analysis gate PASS: real inputs pinned in place',len(pins),'map',digest[:16])


if __name__=='__main__':resource.setrlimit(resource.RLIMIT_AS,(4_000_000_000,4_000_000_000));main()
