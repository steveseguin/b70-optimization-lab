"""Whole-arm differencing only; refuse incomplete or confounded class evidence."""
import argparse,hashlib,json,math,statistics
from pathlib import Path
from census_contract import *

def number(v):
    require(type(v) in (int,float) and math.isfinite(v) and v>0,'positive finite interval required')
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

def analyze(doc):
    require(doc.get('schema')=='packet168.census.v1','census stream schema')
    require(doc.get('diagnostic_only') is True and doc.get('model_loads')==1,'one diagnostic load required')
    require(doc.get('order')==list(ORDER),'real arm order differs')
    require(doc.get('engine_identity')=='packet136-bundle8','bundle8 identity')
    require(doc.get('measurement_scope')=='matched_native_emission_interval','isolated replay is not a matched native emission interval')
    rows=doc['observations'];by={}
    for row in rows:
        key=(row['view'],row['prompt_id']);require(key not in by,'duplicate observation');by[key]=row
    require(set(by)=={(v,i)for v in ORDER for i in IDS},'incomplete arm/prompt matrix')
    control={v:{i:exact_control(by[v,i])for i in IDS}for v in CONTROLS}
    # No interpolation, no dropping the first control, and no lucky reference.
    control_means={v:statistics.mean(control[v].values())for v in CONTROLS}
    drift=max(control_means.values())/min(control_means.values())-1
    require(drift<=.01,'control drift exceeds1%')
    ranked=[]
    for cls in CLASSES:
        differences={v:[] for v in CONTROLS}
        for pid in IDS:
            r=by[cls,pid]
            require(r.get('diagnostic_only') is True and r.get('reported_tokens')==0,'diagnostic arm emitted a reported token')
            require(r.get('snapshot_restored') is True and r.get('repair_exact') is True,'snapshot/repair proof missing')
            require(r.get('same_verified_schedule') is True,'skip changed acceptance/routing schedule')
            require(r.get('class_coverage_complete') is True,'partial/fused class coverage unresolved')
            require(r.get('replacement_cost_included') is True,'replacement work missing')
            require(r.get('control_shape_sha256')==r.get('arm_shape_sha256') and len(r.get('arm_shape_sha256',''))==64,'shape identity missing')
            require(r.get('control_token_count')==r.get('arm_token_count') and r['arm_token_count']>=32,'bounded token counts differ')
            require(r.get('restore_sensor_checks',0)>=2,'restore sensors missing')
            t=number(r['interval_ms'])
            for v in CONTROLS:differences[v].append(control[v][pid]-t)
        delta={v:statistics.mean(x) for v,x in differences.items()}
        marginal=statistics.median(delta.values())
        ranked.append(dict(kernel_class=cls,measured_marginal_ms_per_token=marginal,
          control_spread_ms=max(delta.values())-min(delta.values()),
          paired_control_differences_ms=delta,share_of_17ms_percent=100*marginal/17,
          conservative_marginal_ms=min(delta.values()),closed_levers=CLOSED[cls]))
    ranked.sort(key=lambda r:r['measured_marginal_ms_per_token'],reverse=True)
    top=[]
    for r in ranked[:2]:
        ms=max(0,r['conservative_marginal_ms'])
        # Explicit upper-bound sensitivity, never a candidate measurement.
        top.append(dict(kernel_class=r['kernel_class'],conditional_ceiling_tok_s={
          str(p):1000/(17-ms*p) if ms*p<17 else None for p in (.3,.5)},
          assumption='30%/50% of conservative marginal removed; no replacement overhead;17ms reference, not measured optimized speed'))
    return dict(passed=True,diagnostic_only=True,submission_eligible=False,control_drift=drift,
      control_means_ms=control_means,ranked=ranked,top_two_conditional_ceilings=top)

def write_report(doc,out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    try:result=analyze(doc)
    except (ValueError,KeyError,TypeError) as e:
        result=dict(passed=False,diagnostic_only=True,submission_eligible=False,error=str(e),ranked=[],top_two_conditional_ceilings=[])
    (out/'census-report.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    lines=['# Packet168 diagnostic body census','', 'Diagnostic marginal differences; never a model speed result.','']
    if result['passed']:
        lines+=['| Class | Measured ms/token | Control spread ms | Share of17ms | Closed-lever boundary |','|---|---:|---:|---:|---|']
        for r in result['ranked']:lines.append(f"| {r['kernel_class']} | {r['measured_marginal_ms_per_token']:.6f} | {r['control_spread_ms']:.6f} | {r['share_of_17ms_percent']:.2f}% | {r['closed_levers']} |")
        lines+=['','Top-two **conditional ceilings**, not measured speed:']
        for r in result['top_two_conditional_ceilings']:lines.append(f"- {r['kernel_class']}: {r['conditional_ceiling_tok_s']}; {r['assumption']}")
    else:lines+=['No ranking: '+result['error']]
    (out/'CENSUS.md').write_text('\n'.join(lines)+'\n');return result

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--input',type=Path,required=True);ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();return 0 if write_report(read(a.input),a.output)['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
