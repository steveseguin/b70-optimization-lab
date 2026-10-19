"""Partial body census analyzer. Refuse incomplete or confounded evidence.

Five measured classes come from isolated, exactly repaired body probes on both
ranks (paired control/arm passes in one probe call). Attention (no arm since
v3), cross-card transfer, the split head and every overlap effect are only a subtraction residual:
residual = exact native control ms/token - sum(measured class marginals).
The residual is never called causally isolated, and negative values are kept.
"""
import argparse,json,math,statistics
from pathlib import Path
from census_contract import *

def number(v,positive=True):
    require(type(v) in (int,float) and math.isfinite(v) and (v>0 if positive else True),'finite interval required')
    return v

def exact_control(row):
    require(row['prompt_id'] in IDS,'unknown prompt')
    expected=read(P/'lineage/oracle128'/(row['prompt_id']+'.json'))['tokens']
    tokens=row['tokens']
    require(len(tokens)>=32 and tokens==expected[:len(tokens)],'control oracle mismatch or short control')
    require(row.get('arithmetic')==ARITHMETIC and row.get('cached_tokens')==0,'control identity/cache')
    require(row.get('full_reset') is True and row.get('repairs_complete') is True,'reset/repair incomplete')
    return number(row['interval_ms'])

def historical_control(raw,prompt_id,reset_rows):
    """Same exact-control validator on real parent evidence; no invented arms."""
    require(len(reset_rows)==2 and all(r.get('passed')is True and r.get('allocation_ids_preserved')is True for r in reset_rows),'both real reset receipts required')
    tokens=raw['tokens'][:128];stamps=[r['completed_monotonic']for r in raw['timing_rows'][:min(100,len(tokens))]]
    require(len(stamps)>=32 and all(type(t)in(int,float)and math.isfinite(t)for t in stamps) and all(b>a for a,b in zip(stamps,stamps[1:])),'malformed parent timing stream')
    row=dict(prompt_id=prompt_id,tokens=tokens,arithmetic=raw['arithmetic'],cached_tokens=raw['cached_tokens'],
      full_reset=True,repairs_complete=True,interval_ms=1000*(stamps[-1]-stamps[0])/(len(stamps)-1),
      provenance='historical unchanged control; no diagnostic intervention requiring repair')
    exact_control(row)
    return row

def probe_marginal(row,cls,index):
    """Sum over ranks of the median paired (control - arm) body-pass difference."""
    require(row.get('diagnostic_only') is True and row.get('reported_tokens')==0,'diagnostic arm emitted a reported token')
    require(row.get('setup_exact') is True,'pre-probe setup request not exact')
    require(row.get('arm_code')==ARM_CODES[cls],'arm code differs from registered class')
    probes=row.get('probes')
    require(isinstance(probes,list) and len(probes)==2*REPEATS,'probe rows missing (both ranks x repeats)')
    require([(p.get('rank'),p.get('repeat')) for p in probes]==[(r,k) for r in (0,1) for k in range(REPEATS)],'probe chronology differs')
    by_rank={0:[],1:[]};changed=0
    for p in probes:
        require(p.get('schema')=='packet168.body-probe.v2','probe schema')
        require(p.get('arm')==ARM_CODES[cls] and p.get('prompt_index')==index,'probe identity')
        require(p.get('restore_exact') is True and p.get('repair_exact') is True,'snapshot/repair proof missing')
        require(p.get('diagnostic_only') is True and p.get('reported_tokens')==0,'probe published a token')
        require(p.get('class_coverage_complete') is True,'partial/fused class coverage unresolved')
        require(type(p.get('skipped_sites'))is int and p['skipped_sites']>0,'empty class mask')
        require(type(p.get('route_identity_preserved'))is bool,'route identity receipt missing')
        changed+=not p['route_identity_preserved']
        by_rank[p['rank']].append(number(p['control_ms'])-number(p['arm_ms']))
    return sum(statistics.median(v) for v in by_rank.values()),changed

def analyze(doc):
    require(doc.get('schema')=='packet168.census.v2','census stream schema')
    require(doc.get('diagnostic_only') is True and doc.get('model_loads')==1,'one diagnostic load required')
    require(doc.get('order')==list(ORDER),'real arm order differs')
    require(doc.get('report_classes')==list(REPORT_CLASSES),'exact five-class plus residual coverage required')
    require(doc.get('engine_identity')=='packet136-bundle8','bundle8 identity')
    require(doc.get('measurement_scope')=='native_exact_controls_plus_isolated_body_class_probes','measurement scope')
    require(doc.get('tokens_per_request')==TOKENS and doc.get('repeats_per_probe')==REPEATS,'registered request/probe bounds')
    rows=doc['observations'];by={}
    require([(r['view'],r['prompt_id'])for r in rows]==[(v,i)for v in ORDER for i in IDS],
      'observation chronology differs from registered arm/prompt order')
    for row in rows:
        key=(row['view'],row['prompt_id']);require(key not in by,'duplicate observation');by[key]=row
    control={v:{i:exact_control(by[v,i])for i in IDS}for v in CONTROLS}
    for v in CONTROLS:require(all(len(by[v,i]['tokens'])==TOKENS for i in IDS),'control token boundary differs')
    # No interpolation, no dropping the first control, and no lucky reference.
    control_means={v:statistics.mean(control[v].values())for v in CONTROLS}
    drift=max(control_means.values())/min(control_means.values())-1
    require(drift<=.01,'control drift exceeds1%')
    prompt_drift=max(max(control[v][i] for v in CONTROLS)/min(control[v][i] for v in CONTROLS)-1 for i in IDS)
    ranked=[]
    for cls in CLASSES:
        values=[];changed=0
        for index,pid in enumerate(IDS):
            r=by[cls,pid]
            require(r.get('tokens')==read(P/'lineage/oracle128'/(pid+'.json'))['tokens'][:TOKENS],'setup oracle mismatch')
            m,c=probe_marginal(r,cls,index);values.append(m);changed+=c
        marginal=statistics.median(values)
        ranked.append(dict(kernel_class=cls,measured_marginal_ms_per_body_pass=marginal,
          diagnostic_only=True,causally_isolated=True,isolated_body_probe=True,
          per_prompt_marginals_ms=dict(zip(IDS,values)),prompt_spread_ms=max(values)-min(values),
          conservative_marginal_ms=statistics.quantiles(values,n=4)[0],
          share_of_17ms_percent=100*marginal/17,route_identity_changed_probes=changed,
          route_identity_note='expert count/shapes fixed; changed expert identities are recorded, not hidden',
          closed_levers=CLOSED[cls]))
    ranked.sort(key=lambda r:r['measured_marginal_ms_per_body_pass'],reverse=True)
    total=sum(r['measured_marginal_ms_per_body_pass'] for r in ranked)
    residual_by_control={v:control_means[v]-total for v in CONTROLS}
    residual=dict(kernel_class=RESIDUAL,diagnostic_only=True,causally_isolated=False,
      residual_ms_per_token=statistics.median(residual_by_control.values()),
      paired_control_residual_ms=residual_by_control,
      definition='exact native control ms/token minus sum of five isolated body-pass class marginals; not causally isolated',
      includes=['attention (qsa_*; no arm since v3)','cross-card transfer','split head/argmax/merge','controller/mailbox','overlap and any passes-per-token difference'],
      negative_values_retained=True)
    top=[]
    for r in ranked[:2]:
        ms=max(0,r['conservative_marginal_ms'])
        # Explicit upper-bound sensitivity, never a candidate measurement.
        top.append(dict(kernel_class=r['kernel_class'],conditional_ceiling_tok_s={
          str(p):1000/(17-ms*p) if ms*p<17 else None for p in (.3,.5)},
          assumption='30%/50% of lower-quartile marginal removed; no replacement overhead; 17ms reference; not measured optimized speed'))
    return dict(passed=True,diagnostic_only=True,submission_eligible=False,control_drift=drift,
      per_prompt_control_drift_max=prompt_drift,control_means_ms=control_means,ranked=ranked,residual=residual,
      measured_sum_ms=total,report_classes=list(REPORT_CLASSES),top_two_conditional_ceilings=top,
      units='class marginals: ms per isolated body pass, rank0+rank1 summed; controls: ms per emitted token')

def write_report(doc,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    try:result=analyze(doc)
    except (ValueError,KeyError,TypeError,statistics.StatisticsError) as e:
        result=dict(passed=False,diagnostic_only=True,submission_eligible=False,error=str(e),ranked=[],top_two_conditional_ceilings=[])
    (out/'census-report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    lines=['# Packet168 diagnostic body census','', 'Diagnostic marginal differences; never a model speed result.','']
    if result['passed']:
        lines+=['| Class | Measured ms/body pass | Prompt spread ms | Share of 17 ms | Closed-lever boundary |','|---|---:|---:|---:|---|']
        for r in result['ranked']:lines.append(f"| {r['kernel_class']} | {r['measured_marginal_ms_per_body_pass']:.6f} | {r['prompt_spread_ms']:.6f} | {r['share_of_17ms_percent']:.2f}% | {r['closed_levers']} |")
        lines.append(f"| residual (not causally isolated) | {result['residual']['residual_ms_per_token']:.6f} | — | — | control ms/token − sum of measured classes; includes transfer, split head and overlap |")
        lines+=['',f"Control drift {100*result['control_drift']:.3f}% (view means); largest single-prompt drift {100*result['per_prompt_control_drift_max']:.3f}%.",
          '','Top-two **conditional ceilings**, not measured speed:']
        for r in result['top_two_conditional_ceilings']:lines.append(f"- {r['kernel_class']}: {r['conditional_ceiling_tok_s']}; {r['assumption']}")
    else:lines+=['No ranking: '+result['error']]
    (out/'CENSUS.md').write_text('\n'.join(lines)+'\n');return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();return 0 if write_report(read(a.input),a.output)['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
