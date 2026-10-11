"""CPU census arithmetic and explicitly unmeasured performance scenarios."""
import collections
import hashlib
import json
from pathlib import Path
from expansion import KINDS,RAW,row_bytes
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
CENSUS=ROOT/'experiments/qwen38-flash-next-ud-iq3xxs-b70/packet1/tensor-census.json'
MEM=CENSUS.with_name('memory-admission.json')
RECEIPT=HERE.parent/'packet9-kopt4/receipts-card3-20261011/timing.json'

def main():
    c=json.loads(CENSUS.read_text());m=json.loads(MEM.read_text());receipt=json.loads(RECEIPT.read_text())
    reserve=m['scenario_32k']['estimated_runtime_total_bytes'];baseline=m['historical_plan_reconciliation']['target_resident_bytes']
    policies=[];components={}
    for policy in ('packed','dense','dense_plus_iq2_experts','all_resident_quantized'):
        total=0;cards=[0,0];comp=collections.Counter()
        for t in c['tensors']:
            if t['component'] in ('embedding','ple_lookup'):continue
            expand=(policy!='packed' and t['type'] in KINDS and (t['component']!='routed_experts' or policy=='all_resident_quantized' or (policy=='dense_plus_iq2_experts' and t['type']=='IQ2_S')))
            n=t['bytes']
            if expand:
                k=t['dimensions'][0];n=t['bytes']//(k//KINDS[t['type']][1]*KINDS[t['type']][2])*row_bytes(t['type'],k)
            copies=2 if t['hc_projection_replicated'] else 1
            total+=copies*n;comp[t['component']]+=copies*n
            if copies==2:cards[0]+=n;cards[1]+=n
            else:cards[0 if t['layer'] is not None and t['layer']<24 else 1]+=n
        policies.append(dict(policy=policy,weight_bytes=total,expansion_factor=total/baseline,reserve_bytes=reserve,
            resident_with_reserve_bytes=total+reserve,margin_64_decimal_GB=64000000000-total-reserve,
            historical_capacity_bytes=m['historical_plan_reconciliation']['capacity_bytes'],
            historical_capacity_margin=m['historical_plan_reconciliation']['capacity_bytes']-total-reserve,
            per_card_layer_split_weight_bytes=cards,per_card_with_half_reserve=[v+reserve/2 for v in cards],
            fits_64_decimal_GB_arithmetic=total+reserve<=64000000000,measured_fit=False))
        components[policy]=dict(comp)
    assert policies[0]['weight_bytes']==baseline
    formats=[]
    minbits={'IQ2_S':7,'IQ3_S':5,'IQ3_XXS':7,'Q3_K':3,'IQ4_NL':8,'IQ4_XS':8,'Q6_K':6,'Q8_0':8}
    for kind,(_,b,s,g,meta) in KINDS.items():
        formats.append(dict(type=kind,min_direct_signed_bits=minbits[kind],chosen_code_bits=4 if kind=='Q3_K' else 8,
            source_bytes_per_weight=s/b,resident_bytes_per_weight=row_bytes(kind,b)/b,
            fetched_bytes_per_weight=(.5 if kind=='Q3_K' else 1)+4/g,
            expansion_factor=row_bytes(kind,b)/s,original_metadata_bytes=meta,group=g))
    forecasts=[]
    # Scenario uses expanded code+cached scale traffic, never retained original
    # metadata (which GEMV does not read). Constant 17 us is an allowance, not
    # measured empty-launch overhead. Experts use paired packet9 fused medians.
    import statistics
    for gb in (290,376):
        layers=[]
        for layer in receipt['plan']['layers']:
            dense=0;native=0;traffic=0
            for j in layer['jobs']:
                if j['experts']!=1:continue
                kind=j['type'];n=j['weight_bytes']
                if kind in KINDS:n=j['rows']*j['columns']*((.5 if kind=='Q3_K' else 1)+4/KINDS[kind][3])
                # Raw dispatch preserves both old split passes; expanded kernels
                # fuse the partial reduction in the same workgroup.
                v=next(t['variant'] for t in json.loads((HERE.parent/'packet9-kopt4/dispatch.json').read_text())['tensors'] if t['name']==j['name'])
                launches=2 if kind in RAW and 'split' in v else 1
                dense+=n/(gb*1e6)+.017*launches;native+=launches;traffic+=n
            samples=[next(r for r in rec['summary']['fused'] if r['variant']=='experts_sg32')['median_ms'] for rec in receipt['layers'] if rec['layer']==layer['layer'] and rec['summary']['fused']]
            experts=statistics.median(samples) if samples else 0
            layers.append(dict(layer=layer['layer'],kind=layer['kind'],dense_fetched_bytes=traffic,expert_measured_ms=experts,predicted_ms=dense+experts,native_launches=native+(3 if samples else 0)))
        ms=[l['predicted_ms'] for l in layers];total=34*ms[0]+ms[1]+ms[2]+12*ms[3]+ms[4]+3540/590e6
        forecasts.append(dict(assumed_dense_GB_s=gb,layers=layers,predicted_ms_per_token=total,predicted_tok_s=1000/total))
    out=dict(schema='own-runtime.iq3.packet10.analysis.v1',measured=False,formats=formats,policies=policies,components=components,
        forecasts=forecasts,scope='GEMV-only two-card sequential 36 GDN + 12 QSA; scenarios, not measured decode',
        limits=['17us allowance is not an empty-launch measurement','no nonlinear/state/KV/host lookup/PCIe timing','raw router F32 evidence does not guarantee int8 throughput','full-model quality and native fit pending'],
        head=dict(type='Q6_K',rows=248320,k=2560,packed_bytes=521472000,expanded_resident_bytes=248320*row_bytes('Q6_K',2560),fetched_bytes=248320*2560*1.25,
            predicted_kernel_ms_at_290=248320*2560*1.25/290e6+.017,predicted_kernel_ms_at_376=248320*2560*1.25/376e6+.017),
        inputs={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in (CENSUS,MEM,RECEIPT)},
        reference_tok_s=28.49,packet9_projected_tok_s=16.549939255516705,packed_590_GB_s_ceiling_tok_s=119.16204586884838)
    dispatch=json.loads((HERE.parent/'packet9-kopt4/dispatch.json').read_text())
    table=[]
    for r in dispatch['table']:
        table.append(r)
    (HERE/'dispatch.json').write_text(json.dumps(dict(schema='own-runtime.iq3.packet10.dispatch.v1',
        source='packet9-kopt4/dispatch.json', source_sha256=hashlib.sha256((HERE.parent/'packet9-kopt4/dispatch.json').read_bytes()).hexdigest(),
        rule='dense quantized: split4 when packet9 variant is split4, otherwise SG32; raw unchanged; experts packed fused SG32; head SG32 and local split4 candidates',
        promoted=False,source_table=table),indent=2)+'\n')
    (HERE/'analysis.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps(dict(policies=policies,forecasts=forecasts,head=out['head']),indent=2))
if __name__=='__main__':main()
