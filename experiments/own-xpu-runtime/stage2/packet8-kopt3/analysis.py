#!/usr/bin/env python3
"""Source-operation census and explicitly unmeasured forecasts, no runtime import."""
import json
from pathlib import Path
import statistics
from dispatch import calculate, sha, RECEIPTS
HERE=Path(__file__).resolve().parent
# Per 32 weights, scalar semantic operations BEFORE compiler CSE/vector lowering.
# Excludes address arithmetic, activation widening and output reduction. Includes
# 32 activation multiplies + 32 accumulator adds. Half widening is separate.
# Tuples: table reads, bit shifts, masks, quant/scale/sign int->float, half->float,
# FP multiplies, FP adds, parity(popcount). Conditional integer negation omitted.
COUNTS={
 'IQ2_S':((4,72,72,68,4,104,36,0),(4,70,70,34,.125,68,34,0)),
 'IQ3_S':((8,76,76,68,4,100,32,0),(8,73,73,33,.125,65,32,0)),
 'IQ3_XXS':((32,160,128,96,32,160,64,32),(8,73,72,33,.125,66,33,4)),
 'Q3_K':((0,160,128,64,32,96,32,0),(0,70,68,34,.125,66,32,0)),
 'Q6_K':((0,96,64,36,4,68,32,0),(0,96,64,34,.125,66,32,0)),
 'IQ4_NL':((32,32,32,32,4,64,32,0),(32,32,32,32,1,64,32,0)),
 'IQ4_XS':((32,128,96,64,32,96,32,0),(32,35,34,33,.125,65,32,0)),
 'Q8_0':((0,0,0,32,4,64,32,0),(0,0,0,32,1,64,32,0)),
}
DOMINANT={
 'IQ2_S':'dependent 10-bit grid fetch, unpack/sign conversion; decode8 already shares each octet',
 'IQ3_S':'two dependent 9-bit grid fetches per octet, sign conversion, repeated subscale work',
 'IQ3_XXS':'scalar fallback repeats grid loads, sign parity and packed scale word for every weight',
 'Q3_K':'scalar fallback repeats split six-bit subscale extraction and half widening per weight',
 'Q6_K':'two bit planes per weight; decode8 already hoists scales, so limited decode-only gain',
 'IQ4_NL':'16-level dependent lookup per weight; subgroup register broadcast versus SLM is the lever',
 'IQ4_XS':'six-bit subscale extraction plus nonlinear lookup; format-only, absent from production census',
 'Q8_0':'signed-byte widening and weight/input products; little unpack work, shape/launch dominated',
}
KEYS=('table_reads','shifts','masks','int_to_float','half_to_float','float_multiply','float_add','popcount')
def calculate_analysis():
    rows=[]
    for name,(old,new) in COUNTS.items():
        rows.append(dict(type=name,round2=dict(zip(KEYS,old),fma=0),round3=dict(zip(KEYS,new),fma=0),dominant=DOMINANT[name],
            qualification='format-only scalar comparison; no prior device implementation' if name=='IQ4_XS' else 'source semantic counts; not executed ISA'))
    dispatch=calculate();shapes={tuple(r['key']):r for r in dispatch['table']}
    import sys
    sys.path.insert(0,str(HERE/'tests'))
    from common import plan
    forecasts=[]
    for layer in plan()['layers']:
        for j in layer['jobs']:
            r=shapes[(j['type_id'],j['rows'],j['columns'],j['experts'])]
            v=r['variant'];ms=r['round2_median_ms'][v];passes=2 if v=='splitk4_v1' else 1
            if j['type'] in COUNTS:
                old,new=COUNTS[j['type']]
                # Transparent issue-cost proxy: ordinary scalar op 1, half decode
                # 8, dependent constant grid read 8, hypothetical SLM read 3.
                score=lambda x,lookup: x[0]*lookup+sum(x[1:4])+x[4]*8+sum(x[5:])
                const_ratio=score(new,8)/score(old,8);slm_ratio=score(new,3)/score(old,8)
            else:const_ratio=slm_ratio=1
            predicted=[]
            for ratio,realized in ((max(const_ratio,slm_ratio),.35),(min(const_ratio,slm_ratio),.70)):
                # Retain floor, shorten only residual time. Optimism excludes
                # SLM initialization and shuffle/occupancy regressions: a
                # candidate may be slower than this forecast or the baseline.
                residual=max(0,ms-passes*.017)
                t=passes*.017+residual*(1-realized*(1-ratio))
                predicted.append(min(590,j['packed_active_bytes']/(t*1e6)))
            forecasts.append(dict(name=j['name'],type=j['type'],variant=v,round2_ms=ms,
                round2_GB_s=j['packed_active_bytes']/(ms*1e6),predicted_GB_s=sorted(predicted),
                const_issue_ratio=const_ratio,slm_issue_ratio=slm_ratio))
    # For formats absent from the production timing set, a separately labeled
    # normalized 8 MiB scenario supplies a falsifiable GB/s estimate. Calibrate
    # the proxy issue rate to IQ3_S residual time only; never label it measured.
    score=lambda x,lookup: x[0]*lookup+sum(x[1:4])+x[4]*8+sum(x[5:])
    calibration=[r for r in forecasts if r['type']=='IQ3_S']
    issue_rate=statistics.median((r['round2_GB_s']*r['round2_ms']*1e6/(110/8))*score(COUNTS['IQ3_S'][0],8)/((r['round2_ms']-.017)*1e6) for r in calibration)
    sizes={'IQ2_S':82/8,'IQ3_S':110/8,'IQ3_XXS':98/8,'Q3_K':110/8,'Q6_K':210/8,'IQ4_NL':18,'IQ4_XS':136/8,'Q8_0':34}
    scenarios=[];w=8*1024**2
    for t,(_,new) in COUNTS.items():
        rates=[w/(17000+w/(issue_rate*sizes[t]/score(new,lookup))) for lookup in (8,3)]
        scenarios.append(dict(type=t,packed_bytes=w,predicted_GB_s=[round(min(590,x),2) for x in rates]))
    return dict(schema='own-runtime.iq3.packet8.analysis.v1',measured=False,
        ceiling_GB_s=590,ceiling_source=str(RECEIPTS.relative_to(HERE.parents[3]))+'/ceiling/native.json',
        counts_definition='per32 scalar source operations before compiler CSE, finite scale fast path; fractional half counts amortize one per256; excludes addressing, sign integer negate, shuffles, activation cast and reduction; FMAs zero',
        issue_proxy='ordinary op 1, software half 8, constant table read 8, SLM read 3; uncalibrated assumptions, not ISA cycle costs',
        forecast='T=p*0.017ms+max(0,T_round2-p*0.017ms)*(1-realized*(1-issue_ratio)); realized .35..70; bandwidth cap590; excludes new SLM/shuffle overhead; hypotheses, NOT bounds or measurements',
        counts=rows,forecasts=forecasts,
        normalized_8MiB_scenario=scenarios,scenario_definition="8 MiB packed, one launch, 17us floor; issue proxy calibrated to measured IQ3_S residual; constant/SLM lookup cost assumptions; NOT production-shape forecasts or measured results",
        source_sha256={f:sha(HERE/f) for f in ('decode.hpp','reference.hpp','kernels.cpp','dispatch.json')})
if __name__=='__main__':
    data=calculate_analysis();(HERE/'analysis.json').write_text(json.dumps(data,indent=2)+'\n')
    for t in sorted({r['type'] for r in data['forecasts']}):
        rs=[r for r in data['forecasts'] if r['type']==t]
        print(t,round(statistics.median(r['predicted_GB_s'][0] for r in rs),1),round(statistics.median(r['predicted_GB_s'][1] for r in rs),1))
